cmake_minimum_required(VERSION 3.24)

if(NOT DEFINED RUNTIME_ROOT OR NOT EXISTS "${RUNTIME_ROOT}/sclang.exe")
    message(FATAL_ERROR "RUNTIME_ROOT must name the installed SuperCollider directory")
endif()
if(NOT DEFINED DEPENDENCY_DIRS)
    message(FATAL_ERROR "DEPENDENCY_DIRS must name the native dependency roots")
endif()

file(GLOB_RECURSE plugins LIST_DIRECTORIES FALSE
    "${RUNTIME_ROOT}/plugins/*.scx"
    "${RUNTIME_ROOT}/plugins/*.dll"
)
set(extra_executables
    "${RUNTIME_ROOT}/scsynth.exe"
    "${RUNTIME_ROOT}/supernova.exe"
    ${plugins}
)

# BundleUtilities follows the actual PE import tables, so only DLLs required by
# the headless executables/plugins are copied from vcpkg into the runtime.
set(BU_CHMOD_BUNDLE_ITEMS ON)
include(BundleUtilities)
fixup_bundle(
    "${RUNTIME_ROOT}/sclang.exe"
    "${extra_executables}"
    "${DEPENDENCY_DIRS}"
)
verify_app("${RUNTIME_ROOT}/sclang.exe")
