# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

`src/foamscope/` is a Python package for monitoring and post-processing OpenFOAM cases. `examples/` holds one worked example of the PyFoam case-template workflow. `README.md` is the user guide. Read it before changing the workflow, and update it when a command, option or path it names changes.

## Terminology

- **Base case**: a folder that holds one flow setup, such as `examples/annulus_stream-plane/`.
- **Case template**: `<base case>/base/<template>/`, an ordinary OpenFOAM case with `*.template` files. Usually one per base case.
- **Case**: a generated run in `<base case>/cases/`. Cases are gitignored. Regenerate a case instead of editing it.

Use these terms. Do not say "case-group" or "rig". Call `foamscope` "the package".

## Commands

OpenFOAM and PyFoam commands run in an OpenFOAM v2606 shell (openfoam.com release; on macOS, gerlero's openfoam-app, started with `openfoam`) with the Python environment active.

```bash
pip install -e ".[examples,test]"         # the package (editable), PyFoam, matplotlib, pyvista; gmsh (examples), pytest (test)
pytest                                    # tests in tests/
foam-monitor cases/<name>                 # live plots of postProcessing .dat files (python -m foamscope.monitor)
foam-pv cases/<name> [--save]             # ParaView publication view (python -m foamscope.pv)
python examples/geometry/annulus.py --help   # mesh builders also run standalone

cd examples/annulus_stream-plane          # PyFoam commands run from the base case folder
pyFoamPrepareCase.py cases/<name> --clone-case=base/annulus-2D [--parameter-file=...] [--values-string="{'speed_rpm':200}"]
(cd cases/<name> && pimpleFoam > log.pimpleFoam)
python post/couette_figure.py cases/<name>
```

`pyFoamPrepareCase.py cases/<name>` without `--clone-case` rebuilds the case from its own copy of the template. It does not pick up later edits to `base/`. To test a template change, generate a new case.

## How a case is built

`pyFoamPrepareCase.py` runs a chain that spans several files:

1. `default.parameters` (lab units: mm, rpm, mPa s) plus any overrides from `--parameter-file` and `--values-string`.
2. `derivedParameters.py` runs with every parameter as a Python variable and uses `foamscope.units` to compute SI values (`Ri`, `Ro`, `ecc`, `omega`, `nu`). Every name left defined becomes a parameter, so temporary names, such as imported modules, must be `del`eted at the end.
3. Every `foo.template` is rendered to `foo`. Placeholders are `|-expr-|` (Python expressions allowed). `$$` lines are Python assignments. `<!--(if ...)-->`, `<!--(elif ...)-->`, `<!--(else)-->` and `<!--(end)-->` lines select between blocks of text.
4. `meshCreate.sh`, rendered from `meshCreate.sh.template` (must be executable), looks for `geometry/` in the case folder and then in each parent folder. It runs the gmsh builder, `gmshToFoam`, sets the patch types with `pyFoamChangeBoundaryType.py`, and runs `checkMesh`.
5. `0.org/` is copied to `0/`. The folder must be named `0.org`. `--clone-case` does not copy `0.orig`.

A new parameter touches `default.parameters`, then `derivedParameters.py` if it needs conversion, then `|-name-|` in a `*.template` file. Rename the file to `*.template` if it was not a template yet.

## Architecture notes

- `paraview_view.py` runs inside ParaView's own Python and cannot import `foamscope`. `pv.py` launches it with `pvbatch` (options on the command line) or the ParaView GUI (options in the `PV_CASE` and `PV_ARGS` environment variables). Do not name a module `paraview.py`: ParaView would import it in place of its own `paraview` package.
- `post.read_case` and `post.read_patch` read cases through pyvista's OpenFOAM reader. They create an empty `<case>.foam` file if the case has none. `post.case_parameters` reads `PyFoamPrepareCaseParameters`.
- `shear.write_fields` runs `postProcess -funcs '(grad(U) writeCellVolumes)'` through the `openfoam` launcher. `volume_samples` and `wall_samples` raise `KeyError` until it has run for that time.
- `monitor.find_series` returns only the newest run of each function object. On a re-run, OpenFOAM writes `<name>_<startTime>.dat` beside the old file. `monitor.read_dat` joins the files of a restart.
- `examples/geometry/common.py` holds the default dimensions and sizing helpers shared by the mesh builders. It is not part of the package. Builders must write MSH 2.2 ASCII. Gmsh physical-group names become OpenFOAM patch names.
- The annulus-2D mesh is one cell thick in z, with `frontAndBack` of type `empty`. The `bobTorque` output is for that thickness, not per unit length.
