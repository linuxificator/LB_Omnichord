cmake_minimum_required(VERSION 3.24)

if(NOT DEFINED RUNTIME_APP OR NOT EXISTS "${RUNTIME_APP}")
    message(FATAL_ERROR "RUNTIME_APP must name the installed SuperCollider.app")
endif()
if(NOT DEFINED DEPENDENCY_DIRS)
    message(FATAL_ERROR "DEPENDENCY_DIRS must name the native dependency roots")
endif()

set(resources "${RUNTIME_APP}/Contents/Resources")
file(GLOB_RECURSE plugins LIST_DIRECTORIES FALSE
    "${resources}/plugins/*.scx"
    "${resources}/plugins/*.dylib"
)
set(extra_executables
    "${resources}/scsynth"
    "${resources}/supernova"
    ${plugins}
)

# BundleUtilities is CMake's platform-native dependency-closure mechanism. It
# copies non-system dylibs once and rewrites every executable/plugin reference
# to the private app bundle. This keeps Homebrew a build dependency only.
set(BU_CHMOD_BUNDLE_ITEMS ON)
include(BundleUtilities)
fixup_bundle("${RUNTIME_APP}" "${extra_executables}" "${DEPENDENCY_DIRS}")
verify_app("${RUNTIME_APP}")
