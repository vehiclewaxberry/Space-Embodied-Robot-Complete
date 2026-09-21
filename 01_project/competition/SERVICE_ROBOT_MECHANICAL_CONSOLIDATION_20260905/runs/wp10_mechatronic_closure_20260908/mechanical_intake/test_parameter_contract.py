"""Synthetic negative cases are parser/physics sanity tests, not satellite validation."""
from pathlib import Path
import unittest, copy, json, hashlib
import numpy as np
from parameter_contract import *

HERE=Path(__file__).resolve().parent
PACKET=json.loads((HERE/'PARAMETER_PACKET.json').read_text(encoding='utf-8'))

class ContractTests(unittest.TestCase):
    def rejects(self, code, call):
        with self.assertRaisesRegex(ValueError, code):
            call()

    def test_length_mm_to_m_anchor(self):
        self.assertEqual(convert(125.15,'mm','m'),.12515)

    def test_inertia_squared_scale(self):
        self.assertEqual(convert(1000000,'kg*mm^2','kg*m^2'),1.)
        self.assertNotEqual(convert(1000000,'kg*mm^2','kg*m^2'),1000.)

    def test_volume_cubed_scale(self):
        self.assertEqual(convert(1000000000,'mm^3','m^3'),1.)

    def test_density_inverse_cubed_scale(self):
        self.assertAlmostEqual(convert(2.7e-6,'kg/mm^3','kg/m^3'),2700.)

    def test_null_remains_unknown(self):
        self.assertIsNone(convert(None,'kg*mm^2','kg*m^2'))

    def test_unit_typo_refused(self):
        with self.assertRaises(KeyError):convert(5,'kgmm','kg*m^2')

    def test_nan_refused(self):
        self.rejects('NONFINITE',lambda:convert(float('nan'),'mm','m'))

    def test_right_handed_rotation_and_translation(self):
        T=[[0,-1,0,125.15],[1,0,0,20],[0,0,1,30],[0,0,0,1]]
        self.assertTrue(validate_transform(T))
        self.assertEqual(transform_mm_to_m(T)[0],[0.,-1.,0.,.12515])

    def test_reflection_refused(self):
        self.rejects('NOT_RIGHT_HANDED',lambda:validate_transform(np.diag([-1,1,1,1])))

    def test_scaled_rotation_refused(self):
        self.rejects('NOT_ORTHOGONAL',lambda:validate_transform(np.diag([1.1,1,1,1])))

    def test_bad_homogeneous_row_refused(self):
        T=np.eye(4);T[3,0]=.1
        self.rejects('HOMOGENEOUS',lambda:validate_transform(T))

    def test_sw_column_major_nonidentity(self):
        T=sw16_to_T_m([0,1,0,-1,0,0,0,0,1,.1,.2,.3,1,0,0,0])
        self.assertEqual(T,[[0.,-1.,0.,.1],[1.,0.,0.,.2],[0.,0.,1.,.3],[0.,0.,0.,1.]])

    def test_sw_scale_refused(self):
        self.rejects('SCALE',lambda:sw16_to_T_m([1,0,0,0,1,0,0,0,1,0,0,0,1000,0,0,0]))

    def test_valid_rotated_inertia(self):
        R=np.array([[1,-1,0],[1,1,0],[0,0,2]])/np.sqrt(2);R[2,2]=1
        I=R@np.diag([1.,2.,3.])@R.T
        self.assertTrue(np.allclose(validate_inertia(I,'kg*m^2')['principal_moments_kg_m2'],[1,2,3]))

    def test_nonsymmetric_inertia_refused(self):
        self.rejects('NOT_SYMMETRIC',lambda:validate_inertia([[1,.1,0],[0,1,0],[0,0,1]],'kg*m^2'))

    def test_negative_principal_inertia_refused(self):
        self.rejects('NOT_PSD',lambda:validate_inertia(np.diag([-1.,2.,2.]),'kg*m^2'))

    def test_triangle_failure_even_positive_psd(self):
        self.rejects('PRINCIPAL_TRIANGLE',lambda:validate_inertia(np.diag([1.,1.,3.]),'kg*m^2'))

    def test_inertia_reference_point_refused(self):
        self.rejects('REFERENCE',lambda:validate_inertia(np.eye(3),'kg*m^2',about='assembly_origin'))

    def test_unknown_inertia_refused(self):
        self.rejects('INERTIA_UNKNOWN',lambda:validate_inertia(None,'kg*m^2'))

    def test_owner_reference_without_children_is_allowed_accounting(self):
        self.assertTrue(validate_mass_selection(PACKET,[],['B601_DM_COMPLETE']))

    def test_b601_whole_and_link_double_count_refused(self):
        self.rejects('DOUBLE_COUNT',lambda:validate_mass_selection(PACKET,['B601_base_link'],['B601_DM_COMPLETE']))

    def test_cic_whole_and_cells_double_count_refused(self):
        self.rejects('DOUBLE_COUNT',lambda:validate_mass_selection(PACKET,['PV0_S1_C01_CIC'],['SOLAR_CIC_WHOLE_VENDOR_REFERENCE']))

    def test_duplicate_token_refused(self):
        self.rejects('DUPLICATE',lambda:validate_mass_selection(PACKET,[],['B601_DM_COMPLETE','B601_DM_COMPLETE']))

    def test_unknown_instance_mass_refused(self):
        self.rejects('INSTANCE_MASS_UNKNOWN',lambda:validate_mass_selection(PACKET,['B601_base_link'],[]))

    def test_reserved_not_usable_zero_mass_body(self):
        body=next(x for x in PACKET['instances'] if not x['physical_mass_applicable'])
        self.rejects('RESERVED',lambda:validate_complete_rigid_body(body))

    def test_current_packet_not_physical_ready(self):
        result=physical_readiness(PACKET)
        self.assertFalse(result['physical_dynamics_ready']);self.assertEqual(result['failure_count'],873)

    def test_true_synthetic_rigid_body_fixture(self):
        body={'physical_mass_applicable':True,'mass':{'estimate':1.,'unit':'kg'},
              'center_of_mass_local':{'estimate':[0,0,0],'unit':'m'},
              'inertia_about_COM_local':{'estimate':np.eye(3).tolist(),'unit':'kg*m^2'}}
        self.assertEqual(validate_complete_rigid_body(body)['principal_moments_kg_m2'],[1,1,1])
        body['mass']['estimate']=None
        self.rejects('MASS_UNKNOWN',lambda:validate_complete_rigid_body(body))

    def test_complete_source_packet_integrity(self):
        self.assertTrue(validate_packet_integrity(PACKET))

    def test_missing_instance_refused(self):
        p=dict(PACKET,instances=PACKET['instances'][:-1])
        self.rejects('INSTANCE_COVERAGE',lambda:validate_packet_integrity(p))

    def test_wrong_metres_translation_refused(self):
        p=copy.deepcopy(PACKET);g=p['instances'][0]['geometry_by_state']['service'];g['T_local_to_S_SI_m'][0][3]*=1000
        self.rejects('SOURCE_TO_SI',lambda:validate_packet_integrity(p))

    def test_unstated_uncertainty_identity_refused(self):
        p=copy.deepcopy(PACKET);del p['instances'][0]['mass']['distribution']
        self.rejects('UNCERTAINTY_IDENTITY',lambda:validate_packet_integrity(p))

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(ContractTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    receipt={'status':'PASS_UNIT_ACCOUNTING_PHYSICS_SANITY_NEGATIVE_CASES' if result.wasSuccessful() else 'FAIL',
        'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
        'test_ids':[name for name in unittest.defaultTestLoader.getTestCaseNames(ContractTests)],
        'scope':'Parser/unit/rigid-body mathematical sanity including adversarial fixtures; no satellite model or control simulation.',
        'native_CAD_COM_executed':False,'scientific_GATE_credit':False,'physical_ready':False,
        'packet_sha256':hashlib.sha256((HERE/'PARAMETER_PACKET.json').read_bytes()).hexdigest(),
        'checker_sha256':hashlib.sha256((HERE/'parameter_contract.py').read_bytes()).hexdigest(),
        'test_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (HERE/'CONTRACT_TESTS.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    raise SystemExit(0 if result.wasSuccessful() else 1)
