#!/usr/bin/env bash

set -euo pipefail

usage() {
  echo "Usage: $0 [parent_directory]" >&2
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ "$#" -gt 1 ]]; then
  usage
  exit 1
fi

parent_dir="${1:-.}"

if [[ ! -d "$parent_dir" ]]; then
  echo "Error: directory '$parent_dir' does not exist." >&2
  exit 1
fi

shopt -s nullglob

renamed_count=0
skipped_count=0

for dir_path in "$parent_dir"/*/; do
  dir_name="$(basename "$dir_path")"

  if [[ "$dir_name" =~ ^([^_]+)_([^_]+)$ ]]; then
    new_name="${BASH_REMATCH[2]}_${BASH_REMATCH[1]}"
    new_path="$parent_dir/$new_name"

    if [[ "$dir_name" == "$new_name" ]]; then
      echo "Skip: '$dir_name' does not need renaming."
      ((skipped_count+=1))
      continue
    fi

    if [[ -e "$new_path" ]]; then
      echo "Skip: '$dir_name' -> '$new_name' (target already exists)."
      ((skipped_count+=1))
      continue
    fi

    mv -- "$dir_path" "$new_path"
    echo "Renamed: '$dir_name' -> '$new_name'"
    ((renamed_count+=1))
  else
    echo "Skip: '$dir_name' does not match pattern part1_part2."
    ((skipped_count+=1))
  fi
done

echo "Done. Renamed: $renamed_count, skipped: $skipped_count."
