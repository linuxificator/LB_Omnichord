idf_component_register(
    SRCS
        "main.c"

    INCLUDE_DIRS
        "."

    REQUIRES
        amy
        esp_psram
        ulp
)


#
# Build the LP-core firmware as a separate binary and
# embed it into the HP application.
#

set(ulp_app_name lp_core_main)

set(ulp_lp_core_sources
    "lp_core/main.c"
)

#
# main.c includes the automatically generated
# lp_core_main.h file.
#
set(ulp_exp_dep_srcs
    "main.c"
)

ulp_embed_binary(
    ${ulp_app_name}
    "${ulp_lp_core_sources}"
    "${ulp_exp_dep_srcs}"
)

target_compile_definitions(${COMPONENT_LIB} PRIVATE GAMMA9001=1)
