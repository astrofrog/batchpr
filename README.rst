About
=====

The aim of this package is to provide an easy way to do automated pull requests
to a selection of repositories and make specific changes to them.

To use this, you should write a Python script in which you import and subclass
the ``Updater`` class, and define the following methods and properties::

    from batchpr import Updater

    class MyUpdater(Updater):

        def process_repo(self):
            # This method should contain any code that you want to run inside
            # the repository to make the changes/updates. You can assume that
            # the current working directory is the repository being processed.
            # This method should return False if it was not able to make the
            # changes, and True if it was.

        @property
        def commit_message(self):
            # The commit message to use when making the changes

        @property
        def pull_request_title(self):
            # The title of the pull request

        @property
        def pull_request_body(self)
            # The main body/description of the pull request

        @property
        def branch_name(self):
            # The name of the branch to use

Once you have defined your updater class, you can log in to GitHub and
run the updater as follows::

    from github import Github
    github = Github('', <password>)

    helper = MyUpdater(github=github)
    helper.run('username/repo')

The ``run`` method can take a single repository or a list of repositories.

When in the ``Updater`` class, the following methods are available:

* ``self.run_command(...)``: should be used for running shell commands (e.g.
  ``git``)

* ``self.warn``: should be used for warning messages

* ``self.error``: should be used for error messages
