#!/usr/bin/env bash
# Setzt für jede Plugin-Version den Tag <plugin>-v<version> auf das erste
# Release (Tag 20*/v*, nach Datum sortiert), das diese Version enthält.
# Bestehende Tags bleiben unverändert; so trägt jeder Lauf auch ältere Releases
# nach. Gibt die neuen Tags aus; mit --push werden sie nach origin gepusht.
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=versions.sh
source scripts/versions.sh
created=()
for release in $(git tag -l '20*' 'v*' --sort=creatordate); do
  for id in $PLUGIN_IDS; do
    version=$(plugin_version "$release" "$id")
    [ -n "$version" ] || continue
    tag="$id-v$version"
    git rev-parse -q --verify "refs/tags/$tag" >/dev/null && continue
    git tag -a "$tag" -m "$id $version (Release $release)" "$release^{commit}"
    created+=("$tag")
    echo "$tag -> $release"
  done
done
if [ "${1:-}" = "--push" ] && [ ${#created[@]} -gt 0 ]; then
  git push origin "${created[@]}"
fi
