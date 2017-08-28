import os
import abc
import subprocess

import requests


GITHUB_RAW_FILENAME = "https://raw.githubusercontent.com/{repo}/master/{filename}"


class Ancillary(object):

    def __init__(self, github, repo_name):
        self.github = github
        self.user = github.get_user()
        self.repo_name = repo_name
        self.repo = None
        self.fork = None

    def run(self):

        self.ensure_repo_set_up()
        self.ensure_fork_set_up()

        self.clone_fork()

        if not self.process():
            print("Process did not complete successfully - will not open a pull request")
            return

        # self.open_pull_request()

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
            self.warn("Branch {0} already exists - aborting".format(self.branch_name))
            return

        # Update to the latest upstream master
        self.run_command('git remote add upstream {0}'.format(self.repo.clone_url))
        self.run_command('git fetch upstream')
        self.run_command('git checkout upstream/master')
        self.run_command('git checkout -b {0}'.format(self.branch_name))

        # Initialize submodules
        self.run_command('git submodule init')
        self.run_command('git submodule update')

    def open_pull_request(self):
        self.run_command('git commit -m "{0}"'.format(self.commit_message))
        self.run_command('git push origin {0}'.format(self.branch_name))
        self.repo.create_pull(title=self.commit_message,
                              body=self.description,
                              base='master',
                              head='{0}:{1}'.format(self.fork.owner.login, self.branch_name))

    def run_command(self, command):
        print('-' * 72)
        print("Running '{0}'".format(command))
        ret = subprocess.call(command, shell=True)
        if ret != 0:
            raise Exception("Command '{0}' failed".format(command))

    @abc.abstractmethod
    def precheck(self):
        pass

    @abc.abstractmethod
    def process(self):
        pass

    @abc.abstractproperty
    def branch_name(self):
        pass
