{ pkgs ? import <nixpkgs> {} }:

let
  python = pkgs.python311;
  pythonPackages = python.pkgs;
in
pkgs.mkShell {
  buildInputs = [
    python
    pythonPackages.pytest
    pythonPackages.pytest-cov
    pythonPackages.pytest-mock
    pythonPackages.gitpython
    pythonPackages.watchdog
    pkgs.git
    pkgs.pre-commit
  ];

  shellHook = ''
    echo "HA Config Sync Addon Development Environment"
    echo "Python: $(python --version)"
    echo "Pytest: $(pytest --version)"
    echo ""
    echo "Available commands:"
    echo "  pytest tests/ -v              # Run tests"
    echo "  pytest tests/ --cov           # Run with coverage"
    echo "  pre-commit run --all-files    # Run pre-commit hooks"
  '';
}
