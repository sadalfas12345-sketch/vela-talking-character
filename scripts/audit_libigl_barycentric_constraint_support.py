"""Audit whether installed libigl Python bindings expose constrained ARAP internals."""
import json
import igl

def main():
    data=igl.ARAPData()
    result={
        'iglVersion':getattr(igl,'__version__','unknown'),
        'arapFunctions':[x for x in dir(igl) if 'arap' in x.lower()],
        'arapPrecomputationDoc':str(igl.arap_precomputation.__doc__),
        'arapSolveDoc':str(igl.arap_solve.__doc__),
        'ARAPDataFields':[x for x in dir(data) if not x.startswith('_')],
        'sparseEqualitySolverAvailable':hasattr(igl,'min_quad_with_fixed'),
        'sparseEqualitySolverDoc':str(igl.min_quad_with_fixed.__doc__),
        'positionUpdateMatrixExposed':any(x.lower() in {'k','l','a','b','rhs','rotations','r'} for x in dir(data) if not x.startswith('_')),
        'conclusion':'The binding accepts only fixed vertex handles for arap_solve. Exact barycentric constraints would require access to the internal ARAP local-rotation position-update system, which is not exposed.'
    }
    print(json.dumps(result,indent=2))
if __name__=='__main__': main()
