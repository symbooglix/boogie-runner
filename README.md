# Boogie Runner

This is a framework for running various Boogie tools on a set of boogie
programs. Supported tools ("runners") include

* [Boogie](https://boogie.codeplex.com/)
* [Boogaloo](https://bitbucket.org/nadiapolikarpova/boogaloo/wiki/Home)
* [Corral](https://corral.codeplex.com/)
* [GPUVerify](http://multicore.doc.ic.ac.uk/tools/GPUVerify/)
* [Symbooglix](FIXME)

# Requirements

* Python >= 3.3
* The Boogie tools (e.g. ``Corral``) that you wish to run built or a Docker
  image containing them.

The following python packages (available via ``pip install <package>``)

* PyYAML
* psutil

# Running

Two tools are provided ``boogie-runner.py`` and ``boogie-batch-runner.py``.

## ``boogie-runner.py``

This tool runs a Boogie tool on a single boogie program and outputs the result
to a YAML file. The tool requires four arguments.

```
$ boogie-runner.py <config_file> <boogie_program> <working_dir> <yaml_output>
```

## ``boogie-batch-runner.py``

This tool runs a Boogie tool over one or more Boogie programs specified in the
``program_list`` and writes the results to a YAML file. The tool requires four arguments.

```
$ boogie-batch-runner.py <config_file> <program_list> <working_dirs_root> <yaml_output>
```

# Command line parameters

## ``config_file``

The configuration file instructs the boogie-runner how to run the tool. Examples
can be seen in the ``configs/`` directory.

The configuration file is stored in a YAML format where the top level datastructure
is a dictionary.

### Top level keys

* ``runner`` - The Runner to use (see the ``BoogieRunner/Runners/`` directory). This
  should be the name of the python module that the runner is available in.

* ``runner_config`` - The configuration to give to the runner. This should be a dictionary.

### ``runner_config`` keys

* ``tool_path`` - Absolute path to tool executable. Note ``~`` will be expanded to the users home directory. Note if using Docker this should be the absolute path to the tool inside the container.
* ``max_memory`` - **Optional** The maximum amount of memory (in MiB) that a single run is allowed to use. By default there is no limit
* ``max_time`` - **Optional** The maximum amount of time (in seconds) that a single run is allowed to use before being killed. By default there is no limit.
* ``additional_args`` **Optional** A list of additional command line arguments to pass to the tool
* ``entry_point`` - **Optional** Specifies the entry point in the Boogie program to use. This will be further explained in another section.
* ``docker`` - **Optional** Specifies that the tool should be run in a [Docker](https://www.docker.com) container. This will be further explained in another section.
* ``env`` - **Optional** Specifies the environment variables to pass when running.
* ``mono_path`` - **Optional** Specfies the absolute path to the mono executable to use if mono is required. Note ``~`` will be expanded to the user's home directory.

### ``entry_point`` key

If this key is not present in ``runner_config`` it is implementation defined what the tool will do.
Note that some runners ignore this key.

This key specifies to use a particular procedure/implementation as the entry point in the Boogie program.

Two different values are currently supported

* The name of the procedure/implementation in the Boogie program as a ``string``.
* A dictionary with a single key ``use_bool_attribute`` that maps to a ``string``. In this case the boogie program will be searched for the first procedure (scanning syntactically from the beginning of the file to the end) that has a boolean attribute with the name specified by ``use_bool_attribute``.

### ``env`` key

If this key is present in ``runner_config`` then if should map to a dictionary which maps environment variable names to values
(string to string). Note a runner may chose to modify the enviroment variables and can override what is specifed in the config file.

### ``docker`` key

If this key is not specified the tool will be run natively. If the key is specified then the tool will be run inside a Docker container.

The ``docker`` key should map to another dictionary which must contain the following keys

* ``image`` - The docker image to use. You should make sure the image is on your machine first (run ``docker images``)
* ``volume`` - The location to mount the native file system (containing the Boogie program and the temporary directory) inside the container (e.g. ``/vol/``)

## ``program_list``

This is a line seperate list of paths to Boogie programs to run. Duplicates are not allowed and
comments are allowed (start the line with a ``#``). The paths may be absolute or relative. If using
relative paths the base can be specified using the ``--rprefix`` command line argument to ``boogie-runner.py``.

# Notes on memory limit

If using mono and without Docker then the memory limit is enforced by passing an environment
variable to mono than limits the heap allocation.

If not using mono and using Docker then the memory limit is enforced by using the ``--memory=``
argument to the ``docker run`` command. **NOTE: You should check that this flag works before
using boogie-runner because this flag has no effect unless your kernel is configured correctly**

If running a native executable directly (i.e. not Mono or Docker) and Linux is
not being used then an exception will be throw as this support is not
implemented currently.

# ``yaml_output``

The output will be written as a YAML file. This will contain a list of dictionaries. Each
dictionary describes the result of a run of a single Boogie program by a tool.

The following keys are written by all runners

* ``program`` - The absolute path the Boogie program that was used.
* ``result`` - The result code (see ``BoogieRunner/ResultType.py``)
* ``total_time`` - The total run time in seconds.
* ``working_directory`` - The working directory that the tool was run in. Each programs
  is run in a unique working directory. Tools may dump output in this directory.
* ``timeout_hit`` - True if the tool timeout was reached, false otherwise.
* ``bug_found`` - True if a bug was found by the tool, false if a bug was definitely not found
  and None if it could not be determined if a bug was found.
