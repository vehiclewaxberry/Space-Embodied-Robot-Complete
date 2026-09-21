"""WP07 whole-system source: 24 parameter-driven local parts plus 573 frozen instances.

All geometry is assembled in the original S frame, millimetres. The unchanged
spacecraft/arm shapes and their three poses are frozen inputs, not newly claimed
parametric or qualified models. No WP06 context set is appended.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys

HERE=Path(__file__).resolve().parent
R=HERE.parent
sys.path.insert(0,'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen  # Install the font guard before any build123d import.
from build123d import Location,Color,import_step
from cadgen.assembly import AssemblyHelper
from OCP.gp import gp_Trsf


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1<<20),b''):
            h.update(block)
    return h.hexdigest()


def parameters():
    return json.loads((HERE/'design_parameters.json').read_text(encoding='utf-8'))


def detached(shape):
    result=type(shape)(shape.wrapped)
    if result.parent is not None or getattr(result,'children',()):
        raise RuntimeError('Unsafe parent-linked shape detachment')
    return result.located(shape.global_location)


def location(T):
    transform=gp_Trsf()
    transform.SetValues(*[float(value) for row in T[:3] for value in row])
    return Location(transform)


def parametric_parts(P,manifest):
    package=manifest['parametric_delta']
    for entry in package['code_sources']+package['catalog_sources']:
        if sha(entry['path'])!=entry['sha256']:
            raise RuntimeError('Pinned WP06 generator changed: '+entry['path'])
    path=Path(package['generator_path'])
    sys.path.insert(0,str(path.parent))
    spec=importlib.util.spec_from_file_location('wp07_pinned_local_assembly',path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if Path(module.design.__file__).resolve()!=path.parent/'side_joint_design.py':
        raise RuntimeError('An unrelated side_joint_design module is already loaded')
    # Replace only this in-memory module binding; frozen WP06 source files are untouched.
    # build123d's direct reader creates no cadgen sidecar cache beside catalog inputs.
    module.import_step=import_step
    result=module.parts(P,include_context=False)
    if set(result)!=set(package['instance_ids']):
        raise RuntimeError('The parameter-driven subset must contain exactly 24 declared IDs')
    return result


def build(state='service',P=None):
    """Build a full source assembly; explicit P changes affect only the 24 local parts."""
    if P is None:
        P=parameters()
    manifest=json.loads((R/'results/INTEGRATION_MANIFEST.json').read_text(encoding='utf-8'))
    if state not in manifest['states']:
        raise ValueError('Unsupported frozen state: '+str(state))
    generated=parametric_parts(P,manifest)
    cache={};assembly=AssemblyHelper('WP07_ROBOT_'+state.upper())
    for row in manifest['states'][state]['instances']:
        if row['geometry_mode']=='PARAMETRIC_WP06_LOCAL_DELTA':
            world=detached(generated[row['id']])
        else:
            key=row['part_key']
            if key not in cache:
                if sha(row['source_step']['path'])!=row['source_step']['sha256']:
                    raise RuntimeError('Frozen STEP source changed: '+key)
                cache[key]=detached(import_step(row['source_step']['path']))
            world=detached(cache[key]).moved(location(row['T_S_local']))
        color=(.72,.66,.50) if row.get('arm_link') else (.08,.19,.39) if 'leaf_' in row['id'] else (.68,.72,.75)
        if row['id'].startswith('WP06'):
            color=(.76,.57,.24)
        assembly.add(world,row['id'],color=Color(*color))
    return assembly.build()
