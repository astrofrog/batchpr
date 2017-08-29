import os
import abc
import six
import sys
import shutil
import tempfile
import subprocess
from textwrap import indent

from github import Github
from termcolor import colored
import requests


GITHUB_RAW_FILENAME = "https://raw.githubusercontent.com/{repo}/master/{filename}"


class BranchExistsException(Exception):
    pass


@six.add_metaclass(abc.ABCMeta)
class Updater(object):

    def __init__(self, token, author_name=None, author_email=None):
        self.github = Github(token)
        self.token = token
        self.user = self.github.get_user()
        self.author_name = author_name
        self.author_email = author_email
        self.repo = None
        self.fork = None

    def info(self, message):
        print(message)

    def run(self, repositories):

        if isinstance(repositories, six.string_types):
            repositories = [repositories]

        start_dir = os.path.abspath('.')

        for repository in repositories:

            print(colored('Processing repository: {0}'.format(repository), 'cyan'))

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

            try:

                os.chdir(directory)

                try:
                    self.clone_fork()
                except BranchExistsException:
                    self.error("    Branch {0} already exists - skipping repository".format(self.branch_name))
                    continue
                except Exception:
                    self.error("    An error occurred when cloning fork - skipping repository")
                    continue

                if not self.process_repo():
                    self.warn("    Skipping repository")
                    return

                self.commit_changes()

                if '--dry' not in sys.argv:

                    try:
                        url = self.open_pull_request()
                        print(colored('    Pull request opened: {0}'.format(url), 'green'))
                    except Exception:
                        self.error("    An error occurred when opening pull request - skipping repository")
                        continue

            finally:

                os.chdir(start_dir)

    def add(self, filename):
        self.run_command('git add {0}'.format(filename))

    def copy(self, filename1, filename2):
        shutil.copy(filename1, filename2)

    def warn(self, message):
        print(colored(message, 'magenta'))

    def error(self, message):
        print(colored(message, 'red'))

    def check_file_exists(self, filename):
        r = requests.get(GITHUB_RAW_FILENAME.format(repo=self.repo_name, filename=filename))
        return r.status_code == 200

    def ensure_repo_set_up(self):
        self.repo = self.github.get_repo(self.repo_name)

    def ensure_fork_set_up(self):
        if self.repo.owner.login != self.user.login:
            self.fork = self.user.create_fork(self.repo)
        else:
            self.fork = self.repo

    def clone_fork(self, dirname='.'):

        # Go to working directory
        os.chdir(dirname)

        # Clone the repository
        self.run_command('git clone --depth 1 {0}'.format(self.fork.ssh_url))
        os.chdir(self.repo.name)

        # Make sure the branch doesn't already exist
        try:
            self.run_command('git checkout origin/{0}'.format(self.branch_name))
        except:
            pass
        else:
            raise BranchExistsException()

        # Update to the latest upstream master
        self.run_command('git remote add upstream {0}'.format(self.repo.clone_url))
        self.run_command('git fetch upstream')
        self.run_command('git checkout upstream/master')
        self.run_command('git checkout -b {0}'.format(self.branch_name))

        # Initialize submodules
        self.run_command('git submodule init')
        self.run_command('git submodule update')

    def commit_changes(self):
        if self.author_name:
            self.run_command('git -c "user.name={0}" '
                             '    -c "user.email={1}" '
                             '    commit -m "{2}"'.format(self.author_name,
                                                          self.author_email,
                                                          self.commit_message))
        else:
            self.run_command('git commit -m "{0}"'.format(self.commit_message))

    def open_pull_request(self):
        self.run_command('git push https://astrobot:{0}@github.com/{1} {2}'.format(self.token, self.fork.full_name, self.branch_name))
        result = self.repo.create_pull(title=self.pull_request_title,
                                       body=self.pull_request_body,
                                       base='master',
                                       head='{0}:{1}'.format(self.fork.owner.login, self.branch_name))
        return result.html_url

    def run_command(self, command):
        print("  > {0}".format(command))
        p = subprocess.Popen(command, shell=True,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT)
        p.wait()
        output = p.communicate()[0].decode('utf-8').strip()
        if ('--verbose' in sys.argv or p.returncode != 0) and output:
            print(indent(output, ' ' * 4))
        if p.returncode == 0:
            return output
        else:
            raise Exception("Command '{0}' failed".format(command))

    @abc.abstractmethod
    def process_repo(self):
        pass

    @abc.abstractproperty
    def branch_name(self):
        pass

    @abc.abstractproperty
    def commit_message(self):
        pass

    @abc.abstractproperty
    def pull_request_body(self):
        pass
