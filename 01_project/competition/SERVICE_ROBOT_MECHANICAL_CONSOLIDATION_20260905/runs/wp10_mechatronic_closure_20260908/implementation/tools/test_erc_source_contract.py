"""Negative tests for source declarations and conditional routes, not hardware tests."""
import itertools, tempfile, unittest, xml.etree.ElementTree as ET
from erc_source_contract import *

class ERCContractTests(unittest.TestCase):
    def test_successful_command_is_not_clean_erc(self):
        report=read(H/'results/POWER_LOOP_ERC.json')
        summary=native_erc_summary(report,0)
        self.assertTrue(summary['command_succeeded'])
        self.assertEqual(summary['errors'],7)
        self.assertFalse(summary['ERC_clean'])
    def test_failed_command_cannot_be_clean(self):
        self.assertFalse(native_erc_summary({'sheets':[]},1)['ERC_clean'])
    def test_empty_success_report_is_not_clean(self):
        self.assertFalse(native_erc_summary({'sheets':[]},0)['ERC_clean'])
    def test_wrong_source_success_report_is_not_clean(self):
        report=read(A/'results/POWER_LOOP_ERC.json');report['source']='other.kicad_sch'
        self.assertFalse(native_erc_summary(report,0)['ERC_clean'])
    def test_missing_sheet_success_report_is_not_clean(self):
        report=read(A/'results/POWER_LOOP_ERC.json');report['sheets'].pop()
        self.assertFalse(native_erc_summary(report,0)['ERC_clean'])
    def test_changed_erc_severity_is_not_clean(self):
        report=read(A/'results/POWER_LOOP_ERC.json');report['included_severities']=['warning']
        self.assertFalse(native_erc_summary(report,0)['ERC_clean'])
    def test_current_source_contract(self):
        self.assertTrue(audit_contract(read(A/'power/ERC_SOURCE_DECLARATIONS.json'))['passed'])
    def test_wrong_flag_net_is_rejected(self):
        contract=read(A/'power/ERC_SOURCE_DECLARATIONS.json')
        contract['declarations'][0]['net']='WP10_INPUT_RETURN'
        self.assertFalse(audit_contract(contract)['passed'])
    def test_forged_flag_uuid_is_rejected(self):
        contract=read(A/'power/ERC_SOURCE_DECLARATIONS.json')
        contract['declarations'][0]['uuid']='forged'
        self.assertFalse(audit_contract(contract)['passed'])
    def test_missing_whitelist_item_is_rejected(self):
        contract=read(A/'power/ERC_SOURCE_DECLARATIONS.json');contract['declarations'].pop()
        self.assertFalse(audit_contract(contract)['passed'])
    def test_disconnected_fuse_not_hidden_by_flag(self):
        tree=ET.parse(A/'ecad/wp10_system.xml')
        for net in tree.getroot().findall('./nets/net'):
            for node in list(net.findall('node')):
                if (node.get('ref'),node.get('pin'))==('F201','2'):net.remove(node)
        with tempfile.TemporaryDirectory(prefix='wp10_erc_test_',dir=A/'logs') as td:
            path=Path(td)/'fault.xml';tree.write(path)
            self.assertFalse(audit_contract(read(A/'power/ERC_SOURCE_DECLARATIONS.json'),xml_path=path)['passed'])
    def test_return_short_not_hidden_by_flag(self):
        tree=ET.parse(A/'ecad/wp10_system.xml')
        for net in tree.getroot().findall('./nets/net'):
            if net.get('name')=='WP10_INPUT_RETURN':net.set('name','WP10_ARM_RETURN')
        with tempfile.TemporaryDirectory(prefix='wp10_erc_test_',dir=A/'logs') as td:
            path=Path(td)/'fault.xml';tree.write(path)
            self.assertFalse(audit_contract(read(A/'power/ERC_SOURCE_DECLARATIONS.json'),xml_path=path)['passed'])
    def test_conditional_topology_256_boolean_states(self):
        names=['source','f201','f202','q201','chb','q203','k1','regen']
        for bits in itertools.product([False,True],repeat=8):
            state=dict(zip(names,bits));out=supply_state(**state)
            self.assertEqual(out['AUX_FUSED'],state['source'] and state['f202'])
            if not state['k1'] and not state['regen']:self.assertFalse(out['ARM_BUS_PLUS'])
            if state['regen']:self.assertTrue(out['ARM_BUS_PLUS'])
            if not state['source'] and not (state['regen'] and state['k1']):self.assertFalse(out['RB_COMMON_DRAIN'])
    def test_open_k1_retains_load_side_regen_not_upstream_source(self):
        out=supply_state(source=False,k1=False,regen=True)
        self.assertTrue(out['ARM_BUS_PLUS']);self.assertFalse(out['RB_COMMON_DRAIN']);self.assertFalse(out['AUX_FUSED'])
    def test_closed_k1_regen_can_power_common_drain(self):
        out=supply_state(source=False,k1=True,q203=False,regen=True)
        self.assertTrue(out['RB_COMMON_DRAIN']);self.assertFalse(out['PRECHARGED_PLUS'])
    def test_aux_remains_when_main_switch_or_main_fuse_open(self):
        self.assertTrue(supply_state(q201=False,f201=False)['AUX_FUSED'])
        self.assertFalse(supply_state(f202=False)['AUX_FUSED'])

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ERCContractTests))
    dump(A/'results/ERC_REGRESSION_TESTS.json',dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),passed=result.wasSuccessful(),boolean_states=256,scope='Source/netlist fault injection and Boolean path semantics only; no dynamic simulation or physical execution',inputs={p.relative_to(A).as_posix():sha(p) for p in [Path(__file__),A/'tools/erc_source_contract.py',A/'ecad/wp10_system.xml',A/'power/ERC_SOURCE_DECLARATIONS.json']},physical_tests_executed=False))
    raise SystemExit(0 if result.wasSuccessful() else 1)
