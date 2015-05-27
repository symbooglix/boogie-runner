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

* [PyYAML](http://pyyaml.org/)
* [psutil](https://github.com/giampaolo/psutil)
* [docker-py](https://github.com/docker/docker-py) (only if using the ``Docker`` backend)

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
* ``env`` - **Optional** Specifies the environment variables to pass when running.
* ``mono_path`` - **Optional** Specfies the absolute path to the mono executable to use if mono is required. Note ``~`` will be expanded to the user's home directory.
* ``mono_args`` - **Optional** A list of additional command line arguments to pass to mono.
* ``copy_program_to_working_directory`` - **Optional** If specified and set to ``true`` input Boogie programs to the runner will be copied to the working directory.
* ``stack_size`` - **Optional** If specified will limit the stack size in KiB. Can be set to ``"unlimited"`` to allow an unlimited stack size.
* ``backend`` - **Optional** If specified sets the backend to use and various options to pass to the backend. This will be further explained in another section.

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

### ``backend`` key

If this key is set then it must map to a dictionary that defines the key ``name`` which should map to the name of a backend to use. Optionally
a key ``config`` may also be specified in this dictionary which maps to another dictionary containing settings for backend specific options.

#### Backends

See the ``BoogierRunner/Backends/`` directory for the implemented backends. The purpose of having different backends is to abstract
the way a tool is executed from the command line used to run it. This gives us the flexibility to easily swap out different methods of
running a tool. For example in the future we might support a ``systemd-run`` or ``lxc`` backend.

The default backend is ``PythonPsutil``.

##### PythonPsUtil

This backend uses the Python ``psutil`` module to run the application and enforce a timeout. The following ``config`` keys are supported.

- ``memory_limit_poll_time_period`` . **Optional** The memory limit is enforced using a period polling
thread. The time period for the poll can be controlled by setting. This key should map to float which is
the polling time period is seconds. If not specified a default time period is used.

##### Docker

This backend uses the Python ``docker-py`` module to run application locally inside a Docker container. The following ``config`` keys are
supported.

- ``image``. The docker image name. E.g. ``symbooglix/symbooglix:ase15``.
- ``skip_tool_check`` **Optional**. If set to ``true`` then the check that checks that ``tool_path`` exists in the Docker image ``image``
  is skipped.

## ``program_list``

This is a line seperate list of paths to Boogie programs to run. Duplicates are not allowed and
comments are allowed (start the line with a ``#``). The paths may be absolute or relative. If using
relative paths the base can be specified using the ``--rprefix`` command line argument to ``boogie-runner.py``.

# ``yaml_output``

The output will be written as a YAML file. This will contain a list of dictionaries. Each
dictionary describes the result of a run of a single Boogie program by a tool.

The following keys are written by all runners

* ``program`` - The absolute path the Boogie program that was used.
* ``total_time`` - The total run time in seconds.
* ``working_directory`` - The working directory that the tool was run in. Each programs
  is run in a unique working directory. Tools may dump output in this directory.
* ``timeout_hit`` - True if the tool timeout was reached, false otherwise.
* ``bug_found`` - True if a bug was found by the tool, false if a bug was definitely not found
  and None if it could not be determined if a bug was found.
* ``failed`` - True if the Runner failed to run correctly.
* ``exit_code`` - The exit code of the run tool. Null if a time out was hit
* ``out_of_memory`` - True if the tool memory limit was reached, false otherwise.
