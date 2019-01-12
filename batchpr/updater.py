"""Module to handle batch updaters."""

import abc
import os
import shutil
import subprocess
import sys
import tempfile
import time
from textwrap import indent

import requests
from github import Github
from termcolor import colored

__all__ = ['BranchExistsException', 'Updater', 'IssueUpdater']


class BranchExistsException(Exception):
    """Exception for when GitHub branch already exists."""
    pass


class Updater(metaclass=abc.ABCMeta):
    """Metaclass to handle batch pull requests.
    For batch issues, use :class:`IssueUpdater`.

    Parameters
    ----------
    token : str
        GitHub token for associated GitHub account.

    author_name : str or `None`, optional
        Author name for GitHub account to credit for the commit,
        if different from the account provided by ``token``.

    author_email : str or `None`, optional
        Author email that goes with ``author_name``.

    Raises
    ------
    ValueError
        ``author_email`` must be provided with ``author_name``.

    """
    def __init__(self, token, author_name=None, author_email=None):
        if author_name is not None and author_email is None:
            raise ValueError('author_email must be provided with author_name')

        self.github = Github(token)
        self.token = token
        self.user = self.github.get_user()
        self.author_name = author_name
        self.author_email = author_email
        self.repo = None
        self.fork = None

    def info(self, message):
        """Print the given info message to terminal."""
        print(message)

    def run(self, repositories, delay=2, dry_run=False):
        """Open pull request, one for each of the given repositories.

        Parameters
        ----------
        repositories : str or list of str
            A single repository (format: ``'username/repon'``) or
            a list of repositories (format: ``['user1/repo1', 'user2/repo2']``)
            to process.

        delay : int, optional
            Delay (in seconds) between processing each repository.
            This is ignored if only one repository is given.

        dry_run : bool
            If `True`, this method does not push the feature branch out nor
            open the actual pull request but still runs all the other steps
            (i.e., forking, branching, and committing the changes).

        """
        if isinstance(repositories, str):
            repositories = [repositories]

        start_dir = os.path.abspath('.')

        for ir, repository in enumerate(repositories):

            if ir > 0:
                time.sleep(delay)

            print(colored(f'Processing repository: {repository}', 'cyan'))

            self.repo_name = repository

            try:
                print('  > Ensuring repository exists')
                self.ensure_repo_set_up()
            except Exception:
                self.error("    An error occurred when trying to get the repository")
                continue

            try:
                print('  > Ensuring fork exists (and creating if not)')
                self.ensure_fork_set_up()
            except Exception:
                self.error("    An error occurred when trying to set up a fork")
                continue

            # Go to temporary directory
            directory = tempfile.mkdtemp()
            print(f'  > Working in {directory}')

            try:
                os.chdir(directory)

                try:
                    self.clone_fork()
                except BranchExistsException:
                    self.error(f"    Branch {self.branch_name} already exists"
                               " - skipping repository")
                    continue
                except Exception:
                    self.error("    An error occurred when cloning fork - "
                               "skipping repository")
                    continue

                if not self.process_repo():
                    self.warn("    Skipping repository")
                    return

                self.commit_changes()

                if not dry_run:
                    try:
                        url = self.open_pull_request()
                        print(colored(f'    Pull request opened: {url}', 'green'))
                    except Exception:
                        self.error("    An error occurred when opening "
                                   "pull request - skipping repository")
                        continue
                else:
                    print('  > Successful dry run (no pull request opened)')

            finally:
                os.chdir(start_dir)

    def add(self, filename):
        """Add the given file to ``git`` staging area."""
        self.run_command(f'git add {filename}')

    def copy(self, filename1, filename2):
        """Copy ``filename1`` to ``filename2``."""
        shutil.copy(filename1, filename2)

    def warn(self, message):
        """Print the given warning message to terminal."""
        print(colored(message, 'magenta'))

    def error(self, message):
        """Print the given error message to terminal."""
        print(colored(message, 'red'))

    def check_file_exists(self, filename):
        """Check if a given file exists in the active repository.

        Parameters
        ----------
        filename : str
            Filename to check.

        Returns
        -------
        exists : bool
            `True` if it exists in ``self.repo_name``, else `False`.

        """
        GITHUB_RAW_FILENAME = ('https://raw.githubusercontent.com/'
                               f'{self.repo_name}/{self.repo.default_branch}/{filename}')
        r = requests.get(GITHUB_RAW_FILENAME)
        return r.status_code == 200

    def ensure_repo_set_up(self):
        """Check if ``self.repo_name`` exists.
        If it does, ``self.repo`` will be populated.
        Otherwise, an exception would be raised.

        """
        self.repo = self.github.get_repo(self.repo_name)

    def ensure_fork_set_up(self):
        """Set up a GitHub fork for ``self.repo`` under the account of
        ``self.user``. However, if the user owns the repo, then fork
        creation is skipped and the repo is used directly.
        If fork creation fails, an exception would be raised.

        """
        if self.repo.owner.login != self.user.login:
            self.fork = self.user.create_fork(self.repo)
        else:
            self.fork = self.repo

    def clone_fork(self, dirname='.'):
        """Clone ``self.fork`` in the given directory.
        Then, create a new branch (``self.branch_name``) in that clone.

        Parameters
        ----------
        dirname : str
            Directory in which to clone.

        Raises
        ------
        BranchExistsException
            Branch to be created already exists.

        Exception
            ``git`` command failed.

        """
        # Go to working directory
        os.chdir(dirname)

        # Clone the repository
        self.run_command(f'git clone --depth 1 {self.fork.ssh_url}')
        os.chdir(self.repo.name)

        # Make sure the branch doesn't already exist
        try:
            self.run_command(f'git checkout origin/{self.branch_name}')
        except:  # noqa
            pass
        else:
            raise BranchExistsException()

        # Update to the latest upstream's default branch (usually "master")
        self.run_command(f'git remote add upstream {self.repo.clone_url}')
        self.run_command('git fetch upstream')
        self.run_command(f'git checkout upstream/{self.repo.default_branch}')
        self.run_command(f'git checkout -b {self.branch_name}')

        # Initialize submodules (this is a no-op if there is no submodule)
        self.run_command('git submodule init')
        self.run_command('git submodule update')

    def commit_changes(self):
        """Commit repo changes in ``git`` staging area.
        If alternate ``self.author_name`` and ``self.author_email`` are
        given, the commit is credited to that GitHub account instead.
        Otherwise, the GitHub account associated with the given token is used.
        Commit message is defined in ``self.commit_message``.
        If commit fails, an exception would be raised.

        """
        if self.author_name and self.author_email:
            self.run_command(f'git -c "user.name={self.author_name}" '
                             f'    -c "user.email={self.author_email}" '
                             f'    commit -m "{self.commit_message}"')
        else:
            self.run_command(f'git commit -m "{self.commit_message}"')

    def open_pull_request(self):
        """Push the feature branch out and create a pull request on GitHub.

        Returns
        -------
        url : str
            URL of the pull request.

        Raises
        ------
        Exception
            ``git`` or GitHub command failed.

        """
        self.run_command(f'git push https://{self.user}:{self.token}@github.com/'
                         f'{self.fork.full_name} {self.branch_name}')
        result = self.repo.create_pull(title=self.pull_request_title,
                                       body=self.pull_request_body,
                                       base=self.repo.default_branch,
                                       head=f'{self.fork.owner.login}:{self.branch_name}')
        return result.html_url

    def run_command(self, command, verbose=False):
        """Run the given shell command.

        Parameters
        ----------
        command : str
            Shell command to run.

        verbose : bool
            Print command output to screen.
            If `False`, it will only be printed on failure.

        Returns
        -------
        output : str
            Command output.

        Raises
        ------
        Exception
            Command failed.

        """
        print(f"  > {command}")
        p = subprocess.Popen(command, shell=True,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT)
        p.wait()
        output = p.communicate()[0].decode('utf-8').strip()
        if (verbose or p.returncode != 0) and output:
            print(indent(output, ' ' * 4))
        if p.returncode == 0:
            return output
        else:
            raise Exception(f"Command '{command}' failed")

    @abc.abstractmethod
    def process_repo(self):
        """This method should contain any code that you want to run inside
        the repository to make the changes/updates. You can assume that
        the current working directory is the repository being processed.
        This method should call :meth:`add` to ``git add`` any files that
        have changed, but should not commit.

        Example code in this method::

            import os

            if os.path.exists('README.md'):
                with open('README.md', 'a') as f:
                    f.write(os.linesep + 'Hello World!')
                self.add('README.md')
                return True
            else:
                return False

        Returns
        -------
        status : bool
            This method should return `False` if it was not able to make the
            changes, and `True` if it was.

        """
        pass

    @abc.abstractproperty
    def branch_name(self):
        """Name for the feature branch from which pull request will be
        opened.

        Example code in this method::

            return 'readme-hello-world'

        """
        pass

    @abc.abstractproperty
    def commit_message(self):
        """Commit message for the change in pull request.

        Example code in this method::

            return "MNT: Add important text to README.rst"

        """
        pass

    @abc.abstractproperty
    def pull_request_title(self):
        """The title of the pull request.

        Example code in this method::

            # Set commit message as the pull request title.
            return self.commit_message

        """
        pass

    @abc.abstractproperty
    def pull_request_body(self):
        """The main body/description of the pull request.

        Example code in this method::

            return "Hello, this is my pull request. Please review."

        """
        pass


class IssueUpdater(Updater):
    """Class to handle batch issues, not pull requests.

    Parameters
    ----------
    token : str
        GitHub token for associated GitHub account.

    issue_title : str
        Title for the issue to be opened.

    issue_body : str
        Body of the issue to be opened.
        Docstring-style with GitHub markdown and emoji syntax is acceptable.

    """
    # NOTE: kwargs currently not used but kept for possible future expansion.
    def __init__(self, token, issue_title, issue_body, **kwargs):
        super(IssueUpdater, self).__init__(token, **kwargs)
        self.issue_title = issue_title
        self.issue_body = issue_body

    def run(self, repositories, delay=2):
        """Open issue, one for each of the given repositories.

        Parameters
        ----------
        repositories : str or list of str
            A single repository (format: ``'username/repon'``) or
            a list of repositories (format: ``['user1/repo1', 'user2/repo2']``)
            to process.

        delay : int, optional
            Delay (in seconds) between processing each repository.
            This is ignored if only one repository is given.

        """
        if isinstance(repositories, str):
            repositories = [repositories]

        for ir, repository in enumerate(repositories):

            if ir > 0:
                time.sleep(delay)

            print(colored(f'Processing repository: {repository}', 'cyan'))

            self.repo_name = repository

            try:
                print('  > Ensuring repository exists')
                self.ensure_repo_set_up()
            except Exception:
                self.error("    An error occurred when trying to get the repository")
                continue

            try:
                url = self.process_repo()
                print(colored(f'    Issue opened: {url}', 'green'))
            except Exception:
                self.error("    An error occurred when opening issue - "
                           "skipping repository")
                continue

    def process_repo(self):
        """Create issue in the active repository from
        ``self.issue_title`` and ``self.issue_body``.

        Returns
        -------
        url : str
            URL of the issue created.

        """
        result = self.repo.create_issue(
            title=self.issue_title, body=self.issue_body)
        return result.html_url

    # The rest of the methods are no-op because they have to be defined
    # according to metaclass, but they are not needed here.

    def branch_name(self):
        pass

    def commit_message(self):
        pass

    def pull_request_title(self):
        pass

    def pull_request_body(self):
        pass
