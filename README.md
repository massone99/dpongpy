# Python project template

A simple template of Python projects, with a rigid file structure, and predisposition for unit testing and release on PyPi.

## Relevant features

- All your project code into a single main package (`dpongpy/`)
- All your project tests into a single test package (`test/`)
- Unit testing support via [`unittest`](https://docs.python.org/3/library/unittest.html)
- Automatic testing on all branches via GitHub Actions
- Semi-automatic versioning via Git
- Packaging support via [`setuptools`](https://setuptools.pypa.io/en/latest/setuptools.html)
- Automatic release on [PyPi](https://pypi.org/) via GitHub Actions and [`semantic-release`](https://semantic-release.gitbook.io)
- Automatic dependencies updates via [Renovate](https://docs.renovatebot.com/)

## Project structure

Overview:
```bash
<root directory>
├── dpongpy/             # main package (should be named after your project)
│   ├── __init__.py         # python package marker
│   └── __main__.py         # application entry point
├── tests/                  # test package (should contain unit tests)
├── .github/                # configuration of GitHub CI
│   └── workflows/          # configuration of GitHub Workflows
│       ├── check.yml       # runs tests on multiple OS and versions of Python
│       └── deploy.yml      # if check succeeds, and the current branch is one of {main, master}, triggers automatic releas on PyPi
├── LICENSE                 # license file (Apache 2.0 by default)
├── pyproject.toml          # project configuration file as prescribed by Poetry
├── renovate.json           # configuration of Renovate bot, for automatic dependency updates
├── requirements.txt        # only declares a dependency on Poetry. DO NOT EDIT THIS FILE
└── release.config.js       # script to release on PyPi, and GitHub via semantic-release
```

## TODO-list for template usage

1. Use this template to create a new GitHub repository, say `dpongpy`
    - this name will also be used to identify the package on PyPi
        + so, we suggest choosing a name which has not been used on PyPi, yet
        + we also suggest choosing a name which is a valid Python package name (i.e. `using_snake_case`)

2. Clone the `dpongpy` repository

3. Open a shell into your local `dpongpy` directory and run
    ```bash
    ./rename-template.sh dpongpy
    ```

    This will coherently rename the template's project name with the one chosen by you (i.e. `dpongpy`, in this example)

4. Commit & push

5. Ensure you like the [Apache 2.0 License](https://www.apache.org/licenses/LICENSE-2.0.html). If you don't, change the content of the `LICENSE` file

6. Ensure the versions-range of Python reported in `pyproject.toml` fits the versions you want to support
    + currently defaults to `>= 3.9`
    + if you change this, please also change the versions of Python tests should be run on in CI, by looking the file `.github/workflows/check.yml`

7. Check the Python version and OS tests should be run on in CI, by looking the file `.github/workflows/check.yml`

8. Add your runtime, development, and build dependencies to `pyproject.toml`

9. Check the other metadata in `pyproject.toml`

10. Change the assignee for pull-requests for automatic dependency updates by editing `renovate.json`
    + currently defaults to @gciatto

11. Add your PyPi credentials as secrets of the GitHub repository
    - `PYPI_USERNAME` (resp. `PYPI_PASSWORD`) for your username (resp. password)
    - this may require you to register on PyPi first

12. Generate a GitHub token and add it as a secret of the GitHub repository, named `RELEASE_TOKEN`
    - cf. <https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens#creating-a-personal-access-token-classic>
    - the token must allow pushing to the repository

13. Put your main (resp. test) code in `dpongpy/` (resp. `test/`)

## How to do stuff

### Run the application using Docker Compose

First is essential to allow X Server connections from the container to the host machine:
```bash
xhost '+local:*'
```
X-server connection can then be disabled using:
```bash
xhost '-local:*'
```
Then, run the application using Docker Compose:

```bash
docker-compose build --no-cache

docker-compose up

```


### Restore dev dependencies

1. Install Poetry if you don't have it yet
    ```bash
    pip install -r requirements.txt
    ```

2. Install the project's dependencies
    ```bash
    poetry install
    ```

### Run unit tests

```bash
poetry run poe test
```

> Tests are automatically run in CI, on all pushes on all branches.
> There, tests are executed on multiple OS (Win, Mac, Ubuntu) and on multiple Python versions.

### Run your code as an application

This will execute the `__main__.py` file in the `dpongpy` package:
```bash
python -m dpongpy
```

or alternatively:
```bash
dpongpy
```

the latter is possible because of the script defined in the `pyproject.toml` file.

### Release a new version on PyPi

New versions are automatically released on PyPi via GitHub Actions, when a push is made on the `main` or `master` branch.

The version number is updated automatically by the `semantic-release` tool, which uses the commit messages to infer the type of the release (major, minor, patch).

It is paramount that the commit messages follow the [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) specification,
in order for `semantic-release` to compute version numbers correctly.
