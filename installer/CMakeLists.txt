cmake_minimum_required(VERSION 3.19)
project(arklight-installer NONE)

# ---------------------------------------------------------------------------
# Stage 3 — Packaging & CI (Architecture.md §5)
#
# Wraps the output of `neu build` (run separately — see gui/ and CI) into
# native installers per OS:
#   Linux:   .deb, .rpm (CPack native generators) + AppImage (custom target,
#            CPack has no built-in AppImage generator)
#   Windows: .msi (WIX)
#   macOS:   .dmg (DragNDrop) + .pkg (productbuild)
#
# This file does not invoke `neu build` itself — it expects
# installer/gui/dist/gui/ to already exist (CI runs `neu build` as its own
# step before configuring/building this project; see
# .github/workflows/installer-build.yml). Keeping the two separate means a
# packaging-only change never needs to re-run the Neutralino build.
# ---------------------------------------------------------------------------

set(ARK_VERSION "1.0.0" CACHE STRING "ARKlight Installer version (mirrors installer/gui/neutralino.config.json)")
set(ARK_GUI_DIST "${CMAKE_CURRENT_SOURCE_DIR}/gui/dist/gui" CACHE PATH "Path to neu build output")
set(ARK_BINARY_NAME "gui" CACHE STRING "cli.binaryName from neutralino.config.json")

if(NOT EXISTS "${ARK_GUI_DIST}")
  message(FATAL_ERROR
    "neu build output not found at ${ARK_GUI_DIST}. Run `neu build` in "
    "installer/gui first (see Architecture.md §5 / Implementation.md Stage 3).")
endif()

# ---------------------------------------------------------------------------
# Linux
# ---------------------------------------------------------------------------
if(CMAKE_SYSTEM_NAME STREQUAL "Linux" OR UNIX AND NOT APPLE)
  set(ARK_LINUX_BIN "${ARK_GUI_DIST}/${ARK_BINARY_NAME}-linux_x64")
  if(NOT EXISTS "${ARK_LINUX_BIN}")
    message(FATAL_ERROR "Expected Linux binary not found: ${ARK_LINUX_BIN}")
  endif()

  # CPack's DEB/RPM generators install under /usr regardless of the local
  # CMAKE_INSTALL_PREFIX (which defaults to /usr/local) — the wrapper has
  # to bake in the path it'll actually land at inside the package, not
  # wherever a plain `cmake --install` would put it.
  set(CPACK_PACKAGING_INSTALL_PREFIX "/usr")
  set(ARK_INSTALL_PREFIX "/usr")

  # Wrapper so the installed command matches the .desktop file's
  # Exec=arklight-installer (neu's binary is named gui-linux_x64, not
  # arklight-installer, and needs resources.neu next to it, not on PATH).
  configure_file(
    "${CMAKE_CURRENT_SOURCE_DIR}/packaging/linux/arklight-installer.sh.in"
    "${CMAKE_CURRENT_BINARY_DIR}/arklight-installer"
    @ONLY
  )

  install(PROGRAMS "${ARK_LINUX_BIN}"
    DESTINATION "share/arklight-installer"
    RENAME "${ARK_BINARY_NAME}-linux_x64")
  install(FILES "${ARK_GUI_DIST}/resources.neu"
    DESTINATION "share/arklight-installer")
  install(PROGRAMS "${CMAKE_CURRENT_BINARY_DIR}/arklight-installer"
    DESTINATION "bin")
  install(FILES "${CMAKE_CURRENT_SOURCE_DIR}/linux/arklight-installer.desktop"
    DESTINATION "share/applications")
  install(FILES "${CMAKE_CURRENT_SOURCE_DIR}/gui/resources/icons/appIcon.png"
    DESTINATION "share/icons/hicolor/256x256/apps"
    RENAME "arklight-installer.png")

  # .ark bundle opener (Architecture.md §7) travels in the same package —
  # it's the counterpart to the installer, not a separate install target.
  install(PROGRAMS "${CMAKE_CURRENT_SOURCE_DIR}/linux/opener/arklight-open"
    DESTINATION "bin")
  install(FILES "${CMAKE_CURRENT_SOURCE_DIR}/linux/opener/arklight-bundle.desktop"
    DESTINATION "share/applications")
  install(FILES "${CMAKE_CURRENT_SOURCE_DIR}/linux/opener/arklight-bundle-mime.xml"
    DESTINATION "share/mime/packages")

  set(CPACK_GENERATOR "DEB;RPM")

  set(CPACK_DEBIAN_PACKAGE_MAINTAINER "Rae ARK <horizonarkstudio@gmail.com>")
  set(CPACK_DEBIAN_PACKAGE_SECTION "devel")
  set(CPACK_DEBIAN_PACKAGE_DEPENDS "python3, python3-venv")
  set(CPACK_DEBIAN_FILE_NAME "DEB-DEFAULT")

  set(CPACK_RPM_PACKAGE_LICENSE "See README.md")
  set(CPACK_RPM_PACKAGE_GROUP "Development/Tools")
  set(CPACK_RPM_PACKAGE_REQUIRES "python3")
  set(CPACK_RPM_FILE_NAME "RPM-DEFAULT")
  set(CPACK_RPM_PACKAGE_DESCRIPTION
    "Installer for ARKlight, the Python-first static site compiler. Installs a system or private Python runtime and registers the .ark bundle opener.")

  # AppImage: no native CPack generator, so this is a plain custom target
  # rather than a CPack generator entry. Run as:
  #   cmake --build . --target appimage
  # (in addition to, not instead of, `cpack` for the .deb/.rpm above).
  find_program(APPIMAGETOOL appimagetool)
  if(APPIMAGETOOL)
    set(APPDIR "${CMAKE_CURRENT_BINARY_DIR}/AppDir")
    add_custom_target(appimage
      COMMAND ${CMAKE_COMMAND} -E make_directory "${APPDIR}/usr/bin"
      COMMAND ${CMAKE_COMMAND} -E make_directory "${APPDIR}/usr/share/arklight-installer"
      COMMAND ${CMAKE_COMMAND} -E make_directory "${APPDIR}/usr/share/applications"
      COMMAND ${CMAKE_COMMAND} -E make_directory "${APPDIR}/usr/share/icons/hicolor/256x256/apps"
      COMMAND ${CMAKE_COMMAND} -E copy "${ARK_LINUX_BIN}" "${APPDIR}/usr/share/arklight-installer/${ARK_BINARY_NAME}-linux_x64"
      COMMAND ${CMAKE_COMMAND} -E copy "${ARK_GUI_DIST}/resources.neu" "${APPDIR}/usr/share/arklight-installer/resources.neu"
      COMMAND ${CMAKE_COMMAND} -E copy "${CMAKE_CURRENT_SOURCE_DIR}/linux/arklight-installer.desktop" "${APPDIR}/usr/share/applications/arklight-installer.desktop"
      COMMAND ${CMAKE_COMMAND} -E copy "${CMAKE_CURRENT_SOURCE_DIR}/linux/arklight-installer.desktop" "${APPDIR}/arklight-installer.desktop"
      COMMAND ${CMAKE_COMMAND} -E copy "${CMAKE_CURRENT_SOURCE_DIR}/gui/resources/icons/appIcon.png" "${APPDIR}/usr/share/icons/hicolor/256x256/apps/arklight-installer.png"
      COMMAND ${CMAKE_COMMAND} -E copy "${CMAKE_CURRENT_SOURCE_DIR}/gui/resources/icons/appIcon.png" "${APPDIR}/arklight-installer.png"
      COMMAND ${CMAKE_COMMAND} -E copy "${CMAKE_CURRENT_SOURCE_DIR}/packaging/linux/AppRun" "${APPDIR}/AppRun"
      COMMAND chmod +x "${APPDIR}/AppRun" "${APPDIR}/usr/share/arklight-installer/${ARK_BINARY_NAME}-linux_x64"
      COMMAND ${APPIMAGETOOL} "${APPDIR}" "${CMAKE_CURRENT_BINARY_DIR}/ARKlight-Installer-x86_64.AppImage"
      COMMENT "Building AppImage via appimagetool"
      VERBATIM
    )
  else()
    message(STATUS "appimagetool not found — 'appimage' target will not be available (run: cmake --build . --target appimage after installing it)")
  endif()

# ---------------------------------------------------------------------------
# Windows
# ---------------------------------------------------------------------------
elseif(CMAKE_SYSTEM_NAME STREQUAL "Windows" OR WIN32)
  set(ARK_WIN_BIN "${ARK_GUI_DIST}/${ARK_BINARY_NAME}-win_x64.exe")
  if(NOT EXISTS "${ARK_WIN_BIN}")
    message(FATAL_ERROR "Expected Windows binary not found: ${ARK_WIN_BIN}")
  endif()

  install(PROGRAMS "${ARK_WIN_BIN}"
    DESTINATION "."
    RENAME "arklight-installer.exe")
  install(FILES "${ARK_GUI_DIST}/resources.neu"
    DESTINATION ".")

  set(CPACK_GENERATOR "WIX")
  set(CPACK_WIX_UPGRADE_GUID "8f2e3a10-4c2b-4e7a-9c1d-arklight0003")
  set(CPACK_PACKAGE_EXECUTABLES "arklight-installer;ARKlight Installer")
  # NOTE: no .ico bundled yet (only resources/icons/appIcon.png exists) —
  # WIX/CPACK_PACKAGE_ICON left unset until one is added. Real gap, not
  # silently worked around.

# ---------------------------------------------------------------------------
# macOS
# ---------------------------------------------------------------------------
elseif(CMAKE_SYSTEM_NAME STREQUAL "Darwin" OR APPLE)
  set(ARK_MAC_BIN "${ARK_GUI_DIST}/${ARK_BINARY_NAME}-mac_universal")
  if(NOT EXISTS "${ARK_MAC_BIN}")
    message(FATAL_ERROR "Expected macOS binary not found: ${ARK_MAC_BIN}")
  endif()

  install(PROGRAMS "${ARK_MAC_BIN}"
    DESTINATION "."
    RENAME "arklight-installer")
  install(FILES "${ARK_GUI_DIST}/resources.neu"
    DESTINATION ".")

  set(CPACK_GENERATOR "DragNDrop;productbuild")
  set(CPACK_DMG_VOLUME_NAME "ARKlight Installer")
  set(CPACK_PRODUCTBUILD_IDENTIFIER "com.arklight.installer")
  # NOTE: no .icns bundled yet — same gap as the Windows .ico, left
  # unset rather than faked.

else()
  message(FATAL_ERROR "Unsupported CMAKE_SYSTEM_NAME: ${CMAKE_SYSTEM_NAME}")
endif()

set(CPACK_PACKAGE_NAME "arklight-installer")
set(CPACK_PACKAGE_VENDOR "Rae ARK")
set(CPACK_PACKAGE_VERSION "${ARK_VERSION}")
set(CPACK_PACKAGE_DESCRIPTION_SUMMARY "Installer for ARKlight, the Python-first static site compiler")
set(CPACK_PACKAGE_CONTACT "horizonarkstudio@gmail.com")
# WIX only accepts .txt/.rtf and productbuild only accepts
# .rtfd/.rtf/.html/.txt for this field — README.md's own extension fails
# both generators even though .deb/.rpm/AppImage don't care. Copy its
# content, byte for byte, into a .txt CPack can actually consume rather
# than renaming/faking a license file that isn't the real README.
set(_ark_license_txt "${CMAKE_CURRENT_BINARY_DIR}/LICENSE.txt")
configure_file("${CMAKE_CURRENT_SOURCE_DIR}/../README.md" "${_ark_license_txt}" COPYONLY)
set(CPACK_RESOURCE_FILE_LICENSE "${_ark_license_txt}")

include(CPack)
