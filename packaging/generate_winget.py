"""Gera os manifests WinGet a partir do EXE real e seu SHA-256 (sem hashes fictícios)."""
import argparse
import hashlib
from pathlib import Path

PACKAGE = "Chimpi-hackintosh.ChimpiAI"
REPO = "https://github.com/Chimpi-hackintosh/ChimpiAI"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--version", required=True)
    p.add_argument("--installer", type=Path, required=True)
    p.add_argument("--output", type=Path, default=Path("release/winget"))
    args = p.parse_args()
    if not args.installer.is_file():
        p.error(f"Instalador não encontrado: {args.installer}")
    version = args.version.removeprefix("v")
    if not version or not all(chunk.isdigit() for chunk in version.split(".")):
        p.error("Use uma versão numérica como 1.1.0")
    digest = hashlib.sha256(args.installer.read_bytes()).hexdigest().upper()
    target = args.output / "manifests" / "c" / "Chimpi-hackintosh" / "ChimpiAI" / version
    target.mkdir(parents=True, exist_ok=True)
    prefix = f"PackageIdentifier: {PACKAGE}\nPackageVersion: {version}\n"
    suffix = "ManifestVersion: 1.9.0\n"
    version_yaml = prefix + "DefaultLocale: pt-BR\nManifestType: version\n" + suffix
    locale_yaml = (
        prefix + "PackageLocale: pt-BR\n"
        "Publisher: Chimpi-hackintosh\n"
        "PackageName: ChimpiAI\n"
        f"PackageUrl: {REPO}\n"
        "License: MIT\n"
        "ShortDescription: Assistente de IA local para Windows com Ollama\n"
        "Description: ChimpiAI oferece chat com modelos de IA executados localmente no Windows usando Ollama.\n"
        "Tags:\n  - ai\n  - ollama\n  - chatbot\n"
        "ManifestType: defaultLocale\n" + suffix
    )
    installer_yaml = (
        prefix + "InstallerType: inno\nScope: user\n"
        "Dependencies:\n  PackageDependencies:\n    - PackageIdentifier: Ollama.Ollama\n"
        "Installers:\n  - Architecture: x64\n"
        f"    InstallerUrl: {REPO}/releases/download/v{version}/{args.installer.name}\n"
        f"    InstallerSha256: {digest}\n"
        "ManifestType: installer\n" + suffix
    )
    (target / f"{PACKAGE}.yaml").write_text(version_yaml, encoding="utf-8")
    (target / f"{PACKAGE}.locale.pt-BR.yaml").write_text(locale_yaml, encoding="utf-8")
    (target / f"{PACKAGE}.installer.yaml").write_text(installer_yaml, encoding="utf-8")
    (args.installer.parent / (args.installer.name + ".sha256")).write_text(
        f"{digest}  {args.installer.name}\n", encoding="utf-8"
    )
    print(f"Manifests criados em {target}; SHA256: {digest}")


if __name__ == "__main__":
    main()
