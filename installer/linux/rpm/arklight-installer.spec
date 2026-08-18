Name:           arklight-installer
Version:        %{_arklight_version}
Release:        1%{?dist}
Summary:        Graphical installer for ARKlight
License:        GPLv3+
URL:            https://github.com/Rae-ARK/ARKlight
BuildArch:      %{_arklight_rpm_arch}

%description
ARKlight Installer finds or installs a compatible Python runtime and
installs the current stable ARKlight release. It does not bundle or
compile ARKlight itself; see installer/README.md for the distribution
model.

%install
mkdir -p %{buildroot}/usr/bin
mkdir -p %{buildroot}/usr/share/applications
install -m 0755 %{_arklight_frozen_bin} %{buildroot}/usr/bin/arklight-installer
install -m 0644 %{_arklight_desktop_file} %{buildroot}/usr/share/applications/arklight-installer.desktop

%files
/usr/bin/arklight-installer
/usr/share/applications/arklight-installer.desktop

%changelog
* Wed Aug 19 2026 Rae ARK <horizonarkstudio@gmail.com> - %{_arklight_version}-1
- Automated build
