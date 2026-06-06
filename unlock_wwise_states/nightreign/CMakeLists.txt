cmake_minimum_required(VERSION 3.5.0)

set(CMAKE_GENERATOR_PLATFORM x64)

project(unlock_wwise_states_nr
  VERSION   "1.0.0"
  LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_INTERPROCEDURAL_OPTIMIZATION TRUE)

# Required for ELDEN RING STL ABI compatibility (must match elden-x).
add_definitions(-D_ITERATOR_DEBUG_LEVEL=0)

include(FetchContent)

# Target ELDEN RING NIGHTREIGN: picks nightreign.exe and the Nightreign
# singleton indices inside elden-x. Must be set before elden-x is configured.
set(ER_NIGHTREIGN ON CACHE BOOL "" FORCE)

FetchContent_Declare(elden-x
  GIT_REPOSITORY        https://github.com/ThomasJClark/elden-x.git
  GIT_TAG               main)

FetchContent_MakeAvailable(elden-x)

add_library(unlock_wwise_states_nr SHARED
  src/dllmain.cpp)

target_include_directories(unlock_wwise_states_nr PRIVATE src)

# elden-x propagates MinHook and enables ER_WITH_HOOKS by default.
target_link_libraries(unlock_wwise_states_nr elden-x)