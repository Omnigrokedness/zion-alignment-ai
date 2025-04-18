{pkgs}: {
  deps = [
    pkgs.pkg-config
    pkgs.glibcLocales
    pkgs.postgresql
    pkgs.openssl
  ];
}
