@echo off

mkdir build
pushd build
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat"
cmake.exe .. -DCMAKE_POLICY_VERSION_MINIMUM=3.5
msbuild.exe unlock_wwise_states_nr.vcxproj /p:configuration=release
copy Release\unlock_wwise_states_nr.dll ..\
popd
pause