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
        shelpersCfg = (shelpers.lib pkgs).eval-shelpers [
          ({ shelp, ... }: {
            shelpers."."."App" = {
              inherit shelp;
              run-app = {
                description = "Run main.py";
                script = ''
                  python3 ./main.py "$@"
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
            };
          })
        ];
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = [
            pkgs.python3
            pkgs.python3Packages.requests
            pkgs.python3Packages.beautifulsoup4
            pkgs.python3Packages.lxml
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

        # App forms of shelpers commands (for `nix run .#run-app`).
        apps = shelpersCfg.apps;

        # Generated shelper script files (used by shelpers wrappers).
        shelpers = shelpersCfg.files;
      }
    );
}
