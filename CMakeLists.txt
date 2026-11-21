cmake_minimum_required(VERSION 3.18)
project(imf_engine CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find Torch if LIBTORCH_PATH is provided
if(DEFINED ENV{LIBTORCH_PATH})
    list(APPEND CMAKE_PREFIX_PATH $ENV{LIBTORCH_PATH})
endif()

find_package(Torch QUIET)

if(Torch_FOUND)
    message(STATUS "LibTorch found at: ${Torch_DIR}")
    add_executable(imf_engine src/imf_engine.cpp)
    target_link_libraries(imf_engine "${TORCH_LIBRARIES}")
    set_property(TARGET imf_engine PROPERTY CXX_STANDARD 17)
else()
    message(WARNING "LibTorch not found in system or LIBTORCH_PATH. Building mock engine wrapper.")
    add_executable(imf_engine src/imf_engine.cpp)
    target_compile_definitions(imf_engine PRIVATE NO_LIBTORCH)
endif()
