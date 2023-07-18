"""Editing the snippets."""

import asyncio
from functools import partial

import pytest

from fixtures import TestFile
from support import Namespace, clean_text, populate

from clippets import core

msg_filter = set([
    'Callback',
    'Layout',
    'Unmount',
    'Update',
    'Mount',
    'Show',
    'Resize',
    'Compose',
    'ScreenResume',
    'ScreenSuspend',
    'Focus',
    'DescendantFocus',
])

def dump(*strings):
    """Dump one ore mor blocks of text."""
    print('--------')
    for text in strings:
        for line in text.splitlines(True):
            print(f'  {line!r}')
        print('--------')


class Runner:
    """Runs the Clippets application in a controlled manner.

    The app is run under the pytest asyncio loop.
    """

    logf = None

    def __init__(self, snippet_file: TestFile, actions: list):
        if self.__class__.logf is None:
            self.__class__.logf = open(
                '/tmp/test.log', 'wt', buffering=1, encoding='utf8')
        print('\n\n\n', file=self.logf)
        print(actions, file=self.logf)
        self.app = core.Clippets(
            Namespace(snippet_file=snippet_file.name), logf=self.logf)
        self.q = asyncio.Queue()
        self.actions = actions
        self.pilot = None
        self.watchdog = None
        self.running = True
        self.tasks = set()

    async def run(self):
        """Run the application."""
        coro =  self.app.run_test(headless=True, message_hook=self.on_msg)
        try:
            async with coro as self.pilot:
                self.get_tasks()
                self.watchdog = asyncio.create_task(
                    self.monitor(), name='watchdog')
                #print("WAIT READY", file=self.logf)
                #await self.wait_for_message_name('Ready')
                #print("APP IS READY", file=self.logf)
                for action in self.actions:
                    print("ACT", action, file=self.logf)
                    await self.apply_action(action)
                await self.pilot.press('ctrl+c')
                print("QUIT", file=self.logf)
        except Exception as exc:       # pylint: disable=broad-exception-caught
            print("OOPS", exc, file=self.logf)
        except SystemExit:
            print("OOPS Exit", file=self.logf)
        print("END OF RUN", file=self.logf)
        self.running = False
        await self.watchdog
        self.get_tasks('LEFT')

    async def monitor(self):
        """Watch for broken tasks."""
        quit = False
        n = 0
        try:
            while self.running:
                n += 1
                i = 0
                known = set()
                for i, task in enumerate(asyncio.all_tasks()):
                    name = task.get_name()
                    known.add(name)
                    if task.done():
                        print("DONE! ::", name, file=self.logf)
                        if (exc := task.exception()):
                            print(
                                "ERROR! ::", exc, name, file=self.logf)
                        quit = quit or  await self.handle_error(name)

                new_tasks = known - self.tasks
                dead_tasks = self.tasks - known
                for name in dead_tasks:
                    print("DEAD! ::", name, file=self.logf)
                    self.tasks.discard(name)
                    quit = quit or await self.handle_error(name)
                for name in new_tasks:
                    print("NEW! ::", name, file=self.logf)
                    self.tasks.add(name)

                #print(f'Checked {i + 1} TASKS', file=self.logf)
                #if i < 6:
                #    for i, task in enumerate(asyncio.all_tasks()):
                #        print("Active! ::", i, task.get_name(), file=self.logf)
                await asyncio.sleep(1)
                if quit and i < 6:
                    break

                #if n == 2:
                #    for i, task in enumerate(asyncio.all_tasks()):
                #        print("Active! ::", i, task.get_name(), file=self.logf)
                #        task.print_stack(file=self.logf)

        except Exception as exc:       # pylint: disable=broad-exception-caught
            print("FAILED! ::", exc, file=self.logf)

        print('Monitor DONE', file=self.logf)

    async def apply_action(self, action):
        """Apply an action."""
        await self.pilot.press(action)

    async def handle_error(self, name):
        """Handle an error during the app run."""
        if name.startswith('run_test Snippets('):
            print("ERROR for:", name, file=self.logf)
            await self.app._shutdown()
            return True
        else:
            return False

    def get_tasks(self, mode='INITIAL'):
        """Yada."""
        for task in asyncio.all_tasks():
            name = task.get_name()
            self.tasks.add(name)
            print(f'{mode} ::', name, file=self.logf)

    def on_msg(self, m):
        """Handle a message gereated by the app."""
        name = m.__class__.__name__
        if name not in msg_filter:
            print(m, file=self.logf)
        self.q.put_nowait(m)

    async def wait_for_message_name(self, name: str):
        """Wait for a given application message."""
        while True:
            m = await self.q.get()
            if m.__class__.__name__ == name:
                break


@pytest.mark.asyncio
async def xtest_move_snippet_within_group(snippet_infile):
    """The position of snippet may be moved within a group."""
    populate(snippet_infile, '''
        Main
          @text@
            Snippet 1
          @text@
            Snippet 2
        Second
          @text@
            Snippet 3
          @text@
            Snippet 4
    ''')
    actions = (
        ['down'] * 3          # Move to Snippet 4
        + ['m']               # Start moving
        + ['up']              # Move insetion point
        + ['enter']           # Complete move
    )
    runner = Runner(snippet_infile, actions)
    await runner.run()
    expect = clean_text('''
        Group: <ROOT>
        KeywordSet:
        Group: Main
        KeywordSet:
        Snippet: 'Snippet 1'
        Snippet: 'Snippet 2'
        Group: Second
        KeywordSet:
        Snippet: 'Snippet 4'
        Snippet: 'Snippet 3'
    ''')
    assert expect == runner.app.groups.full_repr()

    # app.mount(*widgets)
    # app.start_move_snippet(snip.uid())
    # app.action_stop_moving()


@pytest.mark.asyncio
async def xtest_move_snippet_between_groups(snippet_infile):
    """The position of snippet may be moved to a different group."""
    populate(snippet_infile, '''
        Main
          @text@
            Snippet 1
          @text@
            Snippet 2
        Second
          @text@
            Snippet 3
          @text@
            Snippet 4
    ''')
    actions = (
        ['down'] * 3          # Move to Snippet 4
        + ['m']               # Start moving
        + ['up'] * 1          # Move insetion point to prev group
        + ['enter']           # Complete move
    )
    runner = Runner(snippet_infile, actions)
    await runner.run()
    expect = clean_text('''
        Group: <ROOT>
        KeywordSet:
        Group: Main
        KeywordSet:
        Snippet: 'Snippet 1'
        Snippet: 'Snippet 2'
        Snippet: 'Snippet 4'
        Group: Second
        KeywordSet:
        Snippet: 'Snippet 3'
    ''')
    assert expect == runner.app.groups.full_repr()

    # app.mount(*widgets)
    # app.start_move_snippet(snip.uid())
    # app.action_stop_moving()
