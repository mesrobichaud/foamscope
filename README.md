# cfdtools

`cfdtools` is a Python package with tools for OpenFOAM cases: live plots of a
running case, ParaView and matplotlib figures, shear-rate distributions,
mesh-convergence checks and blood viscosity models. It is for OpenFOAM users
who analyse their results in Python. The repository also has a worked example
that builds, runs and plots cases from parameters with gmsh and PyFoam.

## Install

### OpenFOAM

- **OpenFOAM v2606**, the openfoam.com release, installed separately. This is
  the tested version.
  - macOS: [openfoam-app](https://github.com/gerlero/openfoam-app) by gerlero,
    which provides the `openfoam` command used below.
  - Linux and WSL: [openfoam.com/download](https://www.openfoam.com/download).

  Other recent openfoam.com versions will probably work but are untested. The
  openfoam.org releases use different dictionary names and will not run the
  example's templates unchanged.
- **ParaView**, only for `foam-pv`.

### Python

You need Python 3.10 or later, in any environment (conda or venv). From the
root of this repository, in a new environment:

```bash
conda create -n cfd python=3.12 && conda activate cfd    # or: python -m venv .venv && source .venv/bin/activate
pip install -e .
```

This installs gmsh, PyFoam, matplotlib, pyvista and the package, and adds the
`foam-monitor` and `foam-pv` commands. The package is installed in editable
mode, so changes under `src/` apply without reinstalling. Run `pip install -e .`
again if `pyproject.toml` changes.

Optional extras:

```bash
pip install -e ".[notebook]"    # Jupyter kernel, to run the example notebook
pip install -e ".[test]"        # pytest
pytest                          # runs the tests in tests/
```

### Start an OpenFOAM shell

PyFoam runs OpenFOAM programs, so OpenFOAM must be available in the same
shell. Start an OpenFOAM shell with the environment active:

```bash
conda activate cfd
openfoam            # macOS; on Linux, source OpenFOAM's etc/bashrc instead
```

## Tools

The tools read standard OpenFOAM output, so a case does not have to come from
the worked example. The one exception is `post.case_parameters`, which needs a
case built with `pyFoamPrepareCase.py`.

### Monitor a running case

`foam-monitor` plots the `.dat` files that function objects write to
`postProcessing/<function object>/<start time>/`, and redraws them while the
solver runs. It replaces OpenFOAM's `foamMonitor`, which on macOS needs X11,
gnuplot and GNU coreutils. Run it in a second terminal, with the same Python
environment active:

```bash
foam-monitor cases/<name>              # refresh every 1 s
foam-monitor cases/<name> -r 5         # refresh every 5 s
foam-monitor cases/<name> -c 2         # two plots per row
foam-monitor cases/<name> -n 0.05      # only the last 0.05 s of simulated time
foam-monitor cases/<name> --save m.png # save one image and exit
foam-monitor cases                     # a folder of cases: show the running one
```

`foam-monitor` is the same as `python -m cfdtools.monitor`. With no path, it
uses the current folder. The path can be relative to wherever you run the
monitor. For a steady solver, `-n` counts iterations.

- Each function object gets its own plot. `solverInfo` files are shown as
  initial residuals on a log scale.
- Columns smaller than a millionth of the largest column in the same file are
  left out, for example the x and y torque of a 2D case.
- Only the newest run of a case is shown. Files left by earlier runs are
  ignored.
- Given a folder of cases, the monitor shows the case whose `postProcessing`
  files changed most recently, and switches when the next case starts. The
  case shown is in the title.

For a transient solver such as `pimpleFoam`, the flow is fully developed when
the monitored quantity, such as a torque, stops changing. The residuals only
show that each time step converged. For a steady solver such as `simpleFoam`,
check that the residuals have fallen and that the monitored quantity has
stopped changing.

### Show a 2D case in ParaView

`foam-pv` opens a case in ParaView with a publication view already set up:
white background, parallel projection, no orientation axes, flat colours, the
Cool to Warm colour map, a colour bar, and the camera along the mesh's thin
direction. With `--save`, it writes the view to an image without opening a
window.

```bash
foam-pv cases/<name>                 # ParaView window
foam-pv                              # from inside a case folder
foam-pv cases/<name> --save          # image only, no window: cases/<name>/figures/paraview_U.png
foam-pv cases/<name> --save --field p --time 0.1 --range 0 0.1 --size 3000 2000 -o fig.png
```

`foam-pv` is the same as `python -m cfdtools.pv`. It looks for ParaView in
`$PARAVIEW_BIN` (a folder containing `paraview` and `pvbatch`), then on the
`PATH`, then in `/Applications/ParaView*.app` on macOS. The view is defined in
`src/cfdtools/paraview_view.py`, which runs in ParaView's own Python.

### Read results and draw figures

`cfdtools.post` reads a case through pyvista and draws fields with
matplotlib. `plot_field` draws each cell of a 2D mesh as a filled polygon, so
the figure shows the real cells with no interpolation.

```python
import matplotlib.pyplot as plt
from cfdtools import post

mesh, t = post.read_case("cases/<name>")            # latest saved time
post.use_style()
fig, ax = plt.subplots()
pc = post.plot_field(ax, mesh, "U")                 # |U| on the cells
fig.colorbar(pc, ax=ax, label="|U| [m/s]")

z = 0.5 * (mesh.bounds[4] + mesh.bounds[5])         # middle of the mesh thickness
d, uy = post.sample_line(mesh, (0.0055, 0, z), (0.00635, 0, z), "U", which="y")
```

| Function | Does |
|---|---|
| `post.read_case(case, time="latest")` | Reads the mesh and cell fields at one saved time. Creates an empty `.foam` file in the case if it has none |
| `post.read_patch(case, patch, time="latest")` | Reads one boundary patch and its face values, for example `wallShearStress` |
| `post.case_parameters(case)` | Returns the parameter values the case was built with, from `PyFoamPrepareCaseParameters` |
| `post.use_style()` | Sets matplotlib defaults for print figures |
| `post.plot_field(ax, mesh, "U", which="mag")` | Draws a field on the cells of a 2D mesh. `transform=` maps coordinates, for example to unroll an annulus |
| `post.component(values, which)` | Reduces a vector field to its magnitude or one component |
| `post.sample_line(mesh, start, end, "U")` | Samples a field along a line, linearly interpolated between cells |
| `post.cell_centres(mesh)`, `post.cell_vertices(mesh)` | Cell geometry |
| `monitor.find_series(case)`, `monitor.read_dat(paths)` | Time histories from `postProcessing/`, for the newest run |

`sample_line` interpolates between cell centres, so values within half a cell
of a wall are not exact. For example, the velocity at a moving wall reads
slightly below the wall speed. Use cell values when that matters.

### Shear-rate distributions

`cfdtools.shear` gives the distribution of shear rate in the fluid volume,
weighted by cell volume, and on the walls, weighted by face area.

```python
import matplotlib.pyplot as plt
from cfdtools import shear

case = "cases/<name>"
shear.write_fields(case)                  # once per case: runs postProcess to write grad(U) and the cell volumes V
vol = shear.volume_samples(case)          # shear rate of every cell, weighted by cell volume
wall = shear.wall_samples(case)           # shear rate of every wall face, weighted by face area
shear.summary(vol)                        # weighted percentiles, fractions below 1, 10, 100 and 1000 1/s

fig, ax = plt.subplots()
shear.plot_cdf(ax, vol, label="volume")   # fraction of the volume below each shear rate
shear.plot_cdf(ax, wall, label="wall")
```

The shear rate is `sqrt(2 D:D)`, where `D` is the symmetric part of `grad(U)`.
OpenFOAM's viscosity models use the same definition. `wall_samples` uses every
patch of type `wall` unless you give `patches=`. `plot_density` plots the
fraction of the volume or area per decade of shear rate.

`write_fields` runs `postProcess` through the `openfoam` command of
openfoam-app. Without that command, run it yourself in an OpenFOAM shell:

```bash
postProcess -case <case> -funcs '(grad(U) writeCellVolumes)' -latestTime
```

### Mesh convergence

```python
from cfdtools.convergence import gci

r = gci([1.0240, 1.0105, 1.0046], [6600, 14850, 33412])    # one quantity and the cell count on each mesh, coarse to fine
r["p"], r["extrapolated"], r["gci_fine"], r["oscillatory"]
```

`gci()` applies the Grid Convergence Index procedure of Celik et al. (2008),
*J. Fluids Eng.* 130, 078001, to one quantity on three meshes. The default
`dim=2` is for a mesh one cell thick. Use `dim=3` for a 3D mesh. It returns
the observed order `p`, the `extrapolated` zero-cell-size value, and
`gci_fine`, the relative uncertainty of the fine-mesh value. If `oscillatory`
is `True`, the values go up and down with refinement, and the GCI is
unreliable. Add a finer mesh in that case.

### Blood viscosity models

```python
import numpy as np
from cfdtools import visc_models as vm

g = np.logspace(-1, 3, 50)               # shear rate, 1/s
vm.quemada(0.45, g)                      # Quemada with the Das coefficients, mPa s
vm.quemada(0.45, g, variant="cokelet")
vm.mkm5(0.45, g, T=37)                   # MKM5, plasma viscosity corrected from 25 C to 37 C
vm.mkm9(0.45, g, T=37)
vm.carreau(g)                            # Carreau fit compiled by Cho and Kensey (1991)
```

- Hematocrit is a fraction (0.45, not 45). Shear rates are in 1/s and
  viscosities in mPa s. A model returns NaN where it is undefined.
- `quemada`, `mkm5` and `mkm9` take a named coefficient set from
  `QUEMADA_SETS`, `MKM5_SETS` or `MKM9_SETS`, or a dict of your own. The
  sources are in the comments next to each set.
- The single-phase fits compiled by Cho and Kensey (1991) are
  `powell_eyring`, `modified_powell_eyring`, `cross`, `simplified_cross`,
  `modified_cross`, `carreau`, `carreau_yasuda`, `casson`, `power_law` and
  `power_law_davies`.
- `couette_wall_shear_rate(omega, Ri, Ro)` is the Newtonian shear rate at the
  rotating inner wall of a Couette gap.
- The module also turns a viscosity function mu(shear rate) into the table of
  shear rate and kinematic viscosity that OpenFOAM's `strainRateFunction`
  viscosity model reads.

### Unit conversion

`cfdtools.units` converts lab units to SI, so parameter files can keep the
units the values are measured in. The example's `derivedParameters.py` uses
it.

```python
from cfdtools import units

units.rpm_to_rad_s(100)                 # 10.47 rad/s
units.kinematic_viscosity(3.5, 1050)    # nu in m^2/s, from mPa s and kg/m^3
0.5 * units.MM                          # mm to m. Also units.UM, units.RPM and units.MPA_S
```

## Worked example: Couette flow in an annulus

`examples/annulus_stream-plane/` is 2D laminar flow in the r-theta plane
between a rotating inner cylinder (the bob) and a stationary outer cylinder
(the cup). It uses `pimpleFoam` with a Newtonian fluid. The bob axis can be
offset from the cup axis (eccentricity).

This section uses three terms:

- A **base case** is a folder that holds one flow setup. Here it is
  `examples/annulus_stream-plane/`.
- A **case template** is an ordinary OpenFOAM case in `base/<template>/` in
  which a few values are placeholders. Here it is `base/annulus-2D/`.
- A **case** is one run in `cases/<name>/`, generated from a case template
  and a set of parameters.

```
examples/
  geometry/                   gmsh mesh builders
    annulus.py                2D r-theta annulus, optional eccentricity
    common.py                 default dimensions and sizing helpers shared by the builders
  annulus_stream-plane/       base case
    base/annulus-2D/          case template
    post/                     figure script and example notebook
    cases/                    generated cases (not tracked by git)
```

| Folder | Contents | Edit it to change |
|---|---|---|
| `examples/geometry/` | Mesh builders | The geometry or mesh |
| `base/annulus-2D/` | Boundary conditions, models, schemes, solver settings, outputs | The physics or numerics |
| `post/` | Figure script and notebook | The figures |
| `cases/` | Generated cases | Nothing. Regenerate the case instead |

| Template | Mesh | Solver | Patches |
|---|---|---|---|
| `annulus-2D` | `examples/geometry/annulus.py`: 2D r-theta annulus, optional eccentricity | pimpleFoam, laminar, Newtonian | `innerWall` (rotating), `outerWall`, `frontAndBack` (empty) |

Keep anything you want to keep in `base/` or in parameter files. You can
delete a case and generate it again at any time. Mesh files (`*.msh`) are not
tracked by git. Each case builds its own mesh.

Run all commands below in the OpenFOAM shell, from inside the base case
folder:

```bash
cd examples/annulus_stream-plane
```

### 1. Generate a case

```bash
pyFoamPrepareCase.py cases/<name> --clone-case=base/annulus-2D
```

The folder `cases/<name>` must not exist yet. The command copies the case
template to `cases/<name>` and then:

1. Reads `default.parameters` and applies any overrides (see step 2).
2. Runs `derivedParameters.py`, which computes SI values (`Ri`, `Ro`, `ecc`,
   `omega`, `nu`).
3. Fills in every `*.template` file. `foo.template` is written as `foo`.
4. Runs `meshCreate.sh`. gmsh builds the mesh with
   `examples/geometry/annulus.py`, `gmshToFoam` converts it, the patch types
   are set, and `checkMesh` runs.
5. Copies `0.org/` to `0/`.
6. Runs `caseSetup.sh`, if the template has one.

The parameter values used are saved in
`cases/<name>/PyFoamPrepareCaseParameters`, with a readable version in
`PyFoamPrepareCaseParameters.rst`. The mesh output is in `meshCreate.sh.log`.

### 2. Change the parameters

`base/annulus-2D/default.parameters` holds every parameter in lab units:
radii and eccentricity in mm, cell counts, viscosity in mPa s, density in
kg/m^3, bob speed in rpm, and the time step, end time and write interval in
seconds. Override values per run instead of editing that file.

For a single run:

```bash
pyFoamPrepareCase.py cases/ecc02 --clone-case=base/annulus-2D \
    --values-string="{'eccentricity_mm':0.2, 'speed_rpm':200}"
```

For runs you want to keep a record of, write a parameter file in OpenFOAM
dictionary syntax, with no header. A `studies/` folder next to `base/` is a
good place for these files.

```
// studies/ecc02.parameters
eccentricity_mm 0.2;
speed_rpm       200;
```

```bash
pyFoamPrepareCase.py cases/ecc02 --clone-case=base/annulus-2D \
    --parameter-file=studies/ecc02.parameters
```

You can give `--parameter-file` more than once. Later files override earlier
ones. `--automatic-casename` builds the case name from the template name, the
parameter files and the values set.

### 3. Edit the case template

- Every file in the template is a normal OpenFOAM file, and you can edit it
  directly.
- Only files that contain parameters are templates (`*.template`). A
  placeholder is written `|-name-|`, where `name` is defined in
  `default.parameters` or `derivedParameters.py`. Python expressions work,
  for example `|-2*omega-|`.
- In a template, a line that starts with `$$` is a Python assignment.
  `<!--(if ...)-->`, `<!--(elif ...)-->`, `<!--(else)-->` and `<!--(end)-->`
  lines select between blocks of text.
- To turn a fixed value into a parameter:
  1. Add it to `default.parameters` in lab units.
  2. Convert it in `derivedParameters.py`, if needed.
  3. Replace the value in the file with `|-name-|`.
  4. Rename the file to `<file>.template`.
- `derivedParameters.py` runs with every parameter defined as a Python
  variable. Every name it leaves defined becomes a parameter, so `del` any
  temporary names, such as imported modules, at the end.
- Name the initial-conditions folder `0.org`. `pyFoamPrepareCase.py
  --clone-case` does not copy `0.orig`.
- `meshCreate.sh.template` must be executable (`chmod +x`). The generated
  `meshCreate.sh` gets the same permissions.
- `meshCreate.sh` looks for a `geometry/` folder in the case folder and then
  in each parent folder, and uses the first one it finds. For the example
  that is `examples/geometry/`.
- To build a mesh without a case, run the builder from the repository root.
  `python examples/geometry/annulus.py --help` lists its options.

### 4. Run the case

Run the solver named by `application` in the case's `system/controlDict`:

```bash
cd cases/<name>
pimpleFoam > log.pimpleFoam
```

Results:

- Time folders: full fields, saved every `writeInterval`. A transient solver
  names them by time (`0.01/`, `0.02/`, and so on).
- `postProcessing/`: time histories. `bobTorque/0/moment.dat` is the torque on
  the bob, and `residuals/0/solverInfo.dat` holds the residuals.
- `log.pimpleFoam`: the solver log.

The mesh is one cell thick in z, so the torque is for that thickness. Divide
it by the thickness to get the torque per metre of bob length. Open
`<name>.foam` in ParaView to view the fields, or use `foam-pv`.

### 5. Monitor the run

In a second terminal, with the same Python environment active:

```bash
foam-monitor cases/<name>
```

The flow is fully developed when the torque stops changing. See
[Monitor a running case](#monitor-a-running-case) for the options.

### 6. Re-run or rebuild a case

Running the solver again in the same case does not replace
`postProcessing/`. OpenFOAM writes new files next to the old ones
(`moment_0.dat`), and the monitor plots only the newest run.

To delete the results but keep the mesh and setup:

```bash
pyFoamClearCase.py cases/<name>        # removes time folders (except 0) and postProcessing/
```

To regenerate a case with the case's own parameters and templates:

```bash
pyFoamPrepareCase.py cases/<name>
pyFoamPrepareCase.py cases/<name> --no-mesh-create      # keep the existing mesh
pyFoamPrepareCase.py cases/<name> --values-string="{'speed_rpm':200}"
```

This does **not** pick up changes made to `base/` after the case was
created. To use the current template, delete the case and generate it again:

```bash
rm -r cases/<name>
pyFoamPrepareCase.py cases/<name> --clone-case=base/annulus-2D
```

To rebuild only the mesh, run `./meshCreate.sh` inside the case.

### 7. Sweep a parameter

Loop over values in the shell:

```bash
for e in 0.0 0.1 0.2 0.3 0.4; do
  pyFoamPrepareCase.py cases/ecc_$e --clone-case=base/annulus-2D \
      --values-string="{'eccentricity_mm':$e}"
  (cd cases/ecc_$e && pimpleFoam > log.pimpleFoam)
done
```

`foam-monitor cases` shows whichever case is running. PyFoam's
`pyFoamRunParameterVariation.py` can also build and run a sweep from a
`.variations` file.

### 8. Run in parallel

Inside the case:

```bash
pyFoamDecompose.py . 4                        # write system/decomposeParDict, split the mesh into 4
mpirun -np 4 pimpleFoam -parallel > log.pimpleFoam
reconstructPar                                # merge processor*/ back into time folders
```

Parallel runs are only faster for large meshes, with at least about 20,000
cells per process. On Apple silicon, start with one process per performance
core.

### 9. Make figures

ParaView is for looking at results. For figures in a paper, use the scripts
in `post/`, which use `cfdtools.post`:

```bash
python post/couette_figure.py cases/<name>                 # writes cases/<name>/figures/couette.pdf and .png
python post/couette_figure.py cases/<name> --time 0.1 -o fig.pdf
foam-pv cases/<name> --save                                # ParaView image, cases/<name>/figures/paraview_U.png
```

`couette_figure.py` draws two panels:

- (a) Velocity magnitude on the mesh cells, with the annulus unrolled (angle
  against radius) so the gap is visible.
- (b) Tangential velocity across the gap. For a concentric case, it plots the
  cell values against the analytical Couette solution. For an eccentric case,
  it plots the profiles at the narrowest and widest gap.

`post/post_examples.ipynb` shows each `cfdtools.post` function on an
annulus-2D case, including time histories from `postProcessing/`. Set `CASE`
in its first code cell to a case you have run. To run the notebook, install
the kernel once with `pip install -e ".[notebook]"`, then select the
environment's Python as the kernel.

## Adding a base case

1. Create the folder. It can be anywhere, inside or outside this repository.

   ```
   <new base case>/
     base/<template>/
     cases/.gitkeep
   ```

2. Write a mesh builder and put it in a `geometry/` folder, either in the base
   case folder or in a parent folder of it. The builder must write MSH 2.2
   ASCII, the only format `gmshToFoam` reads. Gmsh physical group names
   become the OpenFOAM patch names. Copy `examples/geometry/common.py` next to
   the builder if you want its sizing helpers.
3. Copy the OpenFOAM tutorial closest to the new flow into
   `base/<template>/`:
   - `foamSearch $FOAM_TUTORIALS system/controlDict application` lists the
     solver each tutorial uses.
   - Rename `0` or `0.orig` to `0.org`.
   - Delete the tutorial's `Allrun`, `Allclean` and `blockMeshDict`.
   - Rename the boundary conditions in `0.org/*` to match your patch names.
4. Copy `meshCreate.sh.template` from
   `examples/annulus_stream-plane/base/annulus-2D/`. Change the mesh builder
   command and the patch types (`empty`, `wedge`, `wall`).
5. Get the case running with fixed values first, without parameters or
   templates.
6. Replace the values that should vary with parameters (see
   [Edit the case template](#3-edit-the-case-template)).
7. Add a `solverInfo` function object for the monitor, and function objects
   for the quantities you need (`forces`, `probes`, `fieldAverage`).
8. Test it from inside the base case folder:

   ```bash
   pyFoamPrepareCase.py cases/test --clone-case=base/<template> --values-string="{'endTime':0.01}"
   cd cases/test && pimpleFoam > log.pimpleFoam
   ```

To mesh with `blockMesh` instead of gmsh, keep the tutorial's `blockMeshDict`
and leave out `meshCreate.sh`. `pyFoamPrepareCase.py` runs `blockMesh` when
the case has a `blockMeshDict` and no mesh script.

## License

MIT. See [LICENSE](LICENSE).

This offering is not approved or endorsed by OpenCFD Limited, producer and
distributor of the OpenFOAM software via www.openfoam.com, and owner of the
OPENFOAM® and OpenCFD® trade marks.
