Name:           typetomusic
Version:        1.0.0
Release:        1%{?dist}
Summary:        Turn keyboard typing into MIDI music in real time

License:        MIT
URL:            https://github.com/typetomusic/typetomusic
Source0:        %{name}-%{version}.tar.gz

BuildArch:      noarch

Requires:       python3 >= 3.9
Requires:       python3-qt5
Recommends:     python3-pynput
Recommends:     python3-evdev
Recommends:     python3-fluidsynth
Recommends:     fluidsynth
Recommends:     fluid-soundfont-gm
Recommends:     pipewire
Recommends:     pulseaudio

%description
TypeToMusic turns keyboard input into musical note events in real time.

The app uses a backend abstraction and degrades gracefully:
- Input: X11 backend, Wayland/evdev backend, or limited mode.
- Audio: FluidSynth backend when available, otherwise silent mode.

Missing optional dependencies reduce features but never block startup.

%prep
%setup -q

%build
# Python project; no compile step required.

%install
install -d %{buildroot}/usr/bin
install -d %{buildroot}/usr/share/typetomusic
install -d %{buildroot}/usr/share/applications

install -m 0755 packaging/deb/usr/bin/typetomusic %{buildroot}/usr/bin/typetomusic
install -m 0644 packaging/deb/usr/share/applications/typetomusic.desktop %{buildroot}/usr/share/applications/typetomusic.desktop

cp -a main.py typetomusic requirements.txt %{buildroot}/usr/share/typetomusic/

%files
%license LICENSE
/usr/bin/typetomusic
/usr/share/applications/typetomusic.desktop
/usr/share/typetomusic/main.py
/usr/share/typetomusic/requirements.txt
/usr/share/typetomusic/typetomusic

%changelog
* Wed Apr 16 2026 TypeToMusic Contributors <typetomusic@example.com> - 1.0.0-1
- Cross-distro packaging with optional backend dependencies and graceful fallback runtime.
