@echo off

cargo +nightly build --release --target x86_64-pc-windows-msvc
copy target\x86_64-pc-windows-msvc\release\unlock_wwise_states.dll .\
pause