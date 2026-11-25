#!/bin/zsh
for name in CineHarbor "GC Labs"; do
  for folder in "$HOME/Applications" /Applications; do
    app="$folder/$name.app"
    if [[ -d "$app" ]]; then
      exec open "$app"
    fi
  done
done
printf '%s\n' 'CineHarbor.app was not found in Applications.' >&2
exit 1
