@echo off

MKDIR build
PUSHD build
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat"
cmake.exe .. -DCMAKE_POLICY_VERSION_MINIMUM=3.5
msbuild.exe unlock_wwise_states_nr.vcxproj /p:configuration=release
COPY Release\unlock_wwise_states_nr.dll ..\dist\
POPD
PAUSE