About
-----

The aim of this package is to provide an easy way to do automated pull requests
to a selection of repositories and make specific changes to them. This is currently functional but could be significantly improved, so contributions are welcome!

Using
-----

To use this, you should write a Python script in which you import and subclass
the ``Updater`` class, and define the following methods and properties:

.. code:: python

    from batchpr import Updater

    class MyUpdater(Updater):

        def process_repo(self):
            # This method should contain any code that you want to run inside
            # the repository to make the changes/updates. You can assume that
            # the current working directory is the repository being processed.
            # This method should return False if it was not able to make the
            # changes, and True if it was. This method should call self.add
            # to git add any files that have changed, but should not commit.

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

Once you have defined your updater class, you can run it with:

.. code:: python

    helper = MyUpdater(token=GITHUB_TOKEN)
    helper.run('username/repo')

Where GITHUB_TOKEN is a personal access token for GitHub. If you want to
customize the author of the commit, you can do this with:

.. code:: python

    helper.run('username/repo', author_name=..., author_email=...)

The ``run`` method can take a single repository or a list of repositories.

When in the ``Updater`` class, the following methods are available:

* ``self.run_command(command)``: should be used for running shell commands (e.g.
  ``git``)

* ``self.warn(message)``: should be used for warning messages

* ``self.error(message)``: should be used for error messages

* ``self.add(filename)``: should be used to add files that have changed or are new

* ``self.copy(filename1, filename2)``: can be used to copy files

When running your script, you can add ``--verbose`` to see the output of the
commands, and ``--dry`` to not open pull requests.

Full Example
------------

The following shows an example of an updater that adds a few sentences from the
zen of Python to the README file if present:

.. code:: python

    from batchpr import Updater

    DESCRIPTION = """
    This is an automated update made by the ``batchpr`` tool :robot: - feel free to
    close if it doesn't look good! You can report issues to @astrofrog.
    """

    ADDITION = """
    Beautiful is better than ugly.
    Explicit is better than implicit.
    Simple is better than complex.
    Complex is better than complicated.
    """

    class ExampleUpdater(Updater):

        def process_repo(self):

            if os.path.exists('README.md'):
                with open('README.md', 'a') as f:
                    f.write('\n' + ADDITION)
                self.add('README.md')
                return True
            else:
                return False

        @property
        def commit_message(self):
            return "MNT: Add important text to README.rst"

        @property
        def branch_name(self):
            return 'readme-zen'

        @property
        def pull_request_title(self):
            return self.commit_message

        @property
        def pull_request_body(self):
            return DESCRIPTION.strip()
