cmake_minimum_required(VERSION 3.14)
project(tcp-to-aedat4-converter
    VERSION 1.0.0
    LANGUAGES C CXX
    DESCRIPTION "Convert raw binary event camera frames over TCP to AEDAT4 format"
)

# C++20 standard
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Build type
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

# Compiler flags
set(CMAKE_CXX_FLAGS_DEBUG "-g -O0 -Wall -Wextra")
set(CMAKE_CXX_FLAGS_RELEASE "-O3 -Wall")

# Find required packages
find_package(dv-processing REQUIRED)
find_package(OpenCV REQUIRED)

# Print found packages info
message(STATUS "Found dv-processing: ${dv-processing_VERSION}")
message(STATUS "Found OpenCV: ${OpenCV_VERSION}")

# Main converter executable
add_executable(converter
    src/main.cpp
    src/tcp_receiver.cpp
    src/udp_receiver.cpp
    src/frame_unpacker.cpp
)

# Include directories
target_include_directories(converter PRIVATE
    ${CMAKE_SOURCE_DIR}/include
)

# Link libraries
target_link_libraries(converter PRIVATE
    dv::processing
    ${OpenCV_LIBS}
)

# Platform-specific settings
if(WIN32)
    # Windows socket library
    target_link_libraries(converter PRIVATE ws2_32)
endif()

if(UNIX AND NOT APPLE)
    # Linux - link pthread
    target_link_libraries(converter PRIVATE pthread)
endif()

# Install target (optional)
install(TARGETS converter DESTINATION bin)

# =========================================================================
# TESTING
# =========================================================================
option(BUILD_TESTING "Build unit tests" OFF)

if(BUILD_TESTING)
    enable_testing()

    # Fetch Google Test
    include(FetchContent)
    FetchContent_Declare(
        googletest
        GIT_REPOSITORY https://github.com/google/googletest.git
        GIT_TAG v1.14.0
    )
    # Prevent overriding parent project's compiler/linker settings on Windows
    set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
    FetchContent_MakeAvailable(googletest)

    # Create test library with common code
    add_library(converter_lib STATIC
        src/tcp_receiver.cpp
        src/udp_receiver.cpp
        src/frame_unpacker.cpp
    )
    target_include_directories(converter_lib PUBLIC
        ${CMAKE_SOURCE_DIR}/include
    )
    target_link_libraries(converter_lib PUBLIC
        dv::processing
        ${OpenCV_LIBS}
    )
    if(WIN32)
        target_link_libraries(converter_lib PUBLIC ws2_32)
    endif()
    if(UNIX AND NOT APPLE)
        target_link_libraries(converter_lib PUBLIC pthread)
    endif()

    # Unit tests executable
    add_executable(unit_tests
        test/unit/test_config.cpp
        test/unit/test_frame_unpacker.cpp
        test/fixtures/test_frames.hpp
    )
    target_include_directories(unit_tests PRIVATE
        ${CMAKE_SOURCE_DIR}/include
        ${CMAKE_SOURCE_DIR}/test
    )
    target_link_libraries(unit_tests PRIVATE
        converter_lib
        GTest::gtest_main
    )

    # Register tests with CTest
    include(GoogleTest)
    gtest_discover_tests(unit_tests)

    message(STATUS "Testing enabled - unit_tests target available")
endif()

# Print configuration summary
message(STATUS "")
message(STATUS "=== TCP to AEDAT4 Converter Configuration ===")
message(STATUS "Build type: ${CMAKE_BUILD_TYPE}")
message(STATUS "C++ Standard: ${CMAKE_CXX_STANDARD}")
message(STATUS "Install prefix: ${CMAKE_INSTALL_PREFIX}")
message(STATUS "")
