#!/bin/zsh
app="$HOME/Applications/CineHarbor.app"
if [[ ! -d "$app" && -d "$HOME/Applications/GC Labs.app" ]]; then
  app="$HOME/Applications/GC Labs.app"
fi
open "$app"
