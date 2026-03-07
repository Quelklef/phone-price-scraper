{
  description = "Phone price scraper dev shell";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    shelpers.url = "gitlab:platonic/shelpers";
  };

  outputs = inputs@{ self, nixpkgs, flake-utils, shelpers, ... }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
        lib = pkgs.lib;

        python3 = pkgs.python3.withPackages (py-pkgs: [
          py-pkgs.requests
          py-pkgs.beautifulsoup4
          py-pkgs.lxml
        ]);

        shelpersCfg = (shelpers.lib pkgs).eval-shelpers [
          ({ shelp, ... }: {
            shelpers."."."App" = {
              inherit shelp;
              run-app = {
                description = "Run src/main.py";
                script = ''
                  ${lib.getExe python3} ./src/main.py "$@"
                '';
              };
              run-codex = {
                description = "Run OpenAI Codex";
                script = ''
                  [ -d node_modules ] || npm i
                  codex_home=$(realpath ./.codex)
                  echo "Using CODEX_HOME=$codex_home"
                  mkdir -p $codex_home
                  CODEX_HOME="$codex_home" npx codex
                '';
              };
              run-tests = {
                description = "Run Python unittest modules found in the repo";
                script = ''
                  set -euo pipefail

                  repo_root="$(git rev-parse --show-toplevel)"
                  cd "$repo_root"

                  test_files="$(
                    rg --color=never -l '\bunittest\b' src --glob '*.py' \
                      | sort -u
                  )"

                  echo "$test_files" | while IFS= read -r file; do
                    # Normalize any prefixed line noise to a src-relative path.
                    file="src/''${file##*src/}"
                    # Convert src path (e.g. src/deps/timing.py) into module notation (deps.timing) for `python -m`.
                    module="$(echo "$file" | sed -E 's#^src/##; s#\.py$##; s#/#.#g')"
                    echo "[run-tests] python3 -m $module"
                    PYTHONPATH=src ${lib.getExe python3} -m "$module"
                  done
                '';
              };
            };
          })
        ];
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = [
            python3
          ];

          shellHook = ''
            ${shelpersCfg.functions}

            # Make all shelpers functions available in child `bash -lc` shells.
            ${lib.concatMapStringsSep "\n"
              (name: "export -f ${name}")
              (lib.attrNames shelpersCfg.files)}

            shelp
          '';
        };

        apps = {
          default = {
            type = "app";
            program = "${pkgs.writeShellScript "phone-price-scraper" ''
              ${lib.getExe python3} ${./.}/src/main.py "$@"
            ''}";
          };
        };

        # Generated shelper script files (used by shelpers wrappers).
        shelpers = shelpersCfg.files;
      }
    );
}
