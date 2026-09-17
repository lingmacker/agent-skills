#!/bin/zsh
set -euo pipefail

if (( $# != 2 )); then
  print -u2 "Usage: $0 <source.svg-or-image> <output.imageset>"
  exit 64
fi

script_dir=${0:A:h}
renderer="$script_dir/render_menu_bar_icons.py"
requirements="$script_dir/requirements.txt"
venv_dir="$script_dir/.venv"

if python3 -c 'import PIL, resvg_py' >/dev/null 2>&1; then
  exec python3 "$renderer" "$1" "$2"
fi

venv_python="$venv_dir/bin/python"
if [[ ! -x "$venv_python" ]]; then
  print -u2 "Python dependencies are missing; creating $venv_dir"
  python3 -m venv "$venv_dir"
fi

if ! "$venv_python" -c 'import PIL, resvg_py' >/dev/null 2>&1; then
  print -u2 "Installing renderer dependencies into $venv_dir"
  "$venv_python" -m pip install --disable-pip-version-check -r "$requirements"
fi

exec "$venv_python" "$renderer" "$1" "$2"
