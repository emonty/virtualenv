import glob
import io
import os.path
import shutil
import subprocess
import sys

from virtualenv._compat import FileNotFoundError


WHEEL_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "_wheels",
)

SCRIPT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "_scripts",
)


class BaseBuilder(object):

    def __init__(self, destination, python, flavour, system_site_packages=False, clear=False,
                 pip=True, setuptools=True, extra_search_dirs=None,
                 prompt=""):
        # We default to sys.executable if we're not given a Python.
        if python is None:
            python = sys.executable

        # We default extra_search_dirs to and empty list if it's None
        if extra_search_dirs is None:
            extra_search_dirs = []

        # Ensure that our destination is an absolute path
        self.destination = os.path.abspath(destination)

        # Determine the name of our virtual environment
        self.name = os.path.basename(self.destination)

        self.python = python
        self.flavour = flavour
        self.system_site_packages = system_site_packages
        self.clear = clear
        self.pip = pip
        self.setuptools = setuptools
        self.extra_search_dirs = extra_search_dirs
        self.prompt = prompt

    @classmethod
    def check_available(self, python):
        raise NotImplementedError

    def create(self):
        # Clear the existing virtual environment.
        if self.clear:
            self.clear_virtual_environment()

        # Actually Create the virtual environment
        self.create_virtual_environment()

        # Install our activate scripts into the virtual environment
        self.install_scripts()

        # Install the packaging tools (pip and setuptools) into the virtual
        # environment.
        self.install_tools()

    def clear_virtual_environment(self):
        try:
            shutil.rmtree(self.destination)
        except FileNotFoundError:
            pass

    def create_virtual_environment(self):
        raise NotImplementedError

    def install_scripts(self):
        # Determine the list of files based on if we're running on Windows
        files = self.flavour.activation_scripts

        # We just always want add the activate_this.py script regardless of
        # platform.
        files.add("activate_this.py")

        # Determine the special Windows prompt
        win_prompt = self.prompt if self.prompt else "({0})".format(self.name)

        # Go through each file that we want to install, replace the special
        # variables so that they point to the correct location, and then write
        # them into the bin directory
        for filename in files:
            # Compute our source and target paths
            source = os.path.join(SCRIPT_DIR, filename)
            target = os.path.join(self.destination, self.flavour.bin_dir, filename)

            # Write the files themselves into their target locations
            with io.open(source, "r", encoding="utf-8") as source_fp:
                with io.open(target, "w", encoding="utf-8") as target_fp:
                    # Get the content from the sources and then replace the
                    # variables with their final values.
                    win_prompt = self.prompt or "(%s)" % "wat"
                    data = source_fp.read()
                    data = data.replace("__VIRTUAL_PROMPT__", self.prompt)
                    data = data.replace("__VIRTUAL_WINPROMPT__", win_prompt)
                    data = data.replace("__VIRTUAL_ENV__", self.destination)
                    data = data.replace("__VIRTUAL_NAME__", self.name)
                    data = data.replace("__BIN_NAME__", self.flavour.bin_dir)

                    # Actually write our content to the target locations
                    target_fp.write(data)

    def install_tools(self):
        # Determine which projects we are going to install
        projects = []
        if self.pip:
            projects.append("pip")
        if self.setuptools:
            projects.append("setuptools")

        # Short circuit if we're not going to install anything
        if not projects:
            return

        # Compute the path to the Python interpreter inside the virtual
        # environment.
        python = os.path.join(self.destination, self.flavour.bin_dir, self.flavour.python_bin)

        # Find all of the Wheels inside of our WHEEL_DIR
        wheels = glob.iglob(os.path.join(WHEEL_DIR, "*.whl"))

        # Construct the command that we're going to use to actually do the
        # installs.
        command = [
            python, "-m", "pip", "install", "--no-index", "--isolated",
            "--find-links", WHEEL_DIR,
        ]

        # Add our extra search directories to the pip command
        for directory in self.extra_search_dirs:
            command.extend(["--find-links", directory])

        # Actually execute our command, adding the wheels from our WHEEL_DIR
        # to the PYTHONPATH so that we can import pip into the virtual
        # environment even though it's not currently installed.
        self.flavour.execute(command + projects, PYTHONPATH=os.pathsep.join(wheels))