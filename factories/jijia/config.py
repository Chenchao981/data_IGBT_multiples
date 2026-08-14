"""Evidence-approved rules for Jijia STS8203 FT CSV exports."""

FACTORY_NAME = "集佳"
DATA_TYPES = ["FT-ALL"]
SOURCE_ENCODING = "gb18030"
SOURCE_SIGNATURE = b"STS8203 Station"
SUPPORTED_PRODUCT = "NCE15TD120BT"
OUTPUT_SHEET_NAME = "DC_Data"

SYSTEM_FIELDS = (
    "SITE_NUM",
    "PART_ID",
    "PASSFG",
    "SOFT_BIN",
    "T_TIME",
    "TEST_NUM",
)

EXPECTED_SOURCE_HEADER = (
    'SITE_NUM', 'PART_ID', 'PASSFG', 'SOFT_BIN', 'T_TIME', 'TEST_NUM',
    'CONT_C3', 'CONT_GH4', 'CONT_GL5', 'CONT_E6', 'CONT_K8', 'V_R5',
    'I_R5', 'V_F5', 'I_F5', 'Ic1', 'Vce', 'VcePeak1', 'Tdoff1',
    'Toff1', 'Tf11', 'Eoff1', 'Tdon', 'Ton', 'Tr', 'Eon1', 'Ets',
    'Didt_Off1', 'Didt_Off_Fast1', 'Didt_Off_Ext1', 'Didt_Off_Ext2',
    'Dvdt_Off1', 'Dvdt_Off_Fast1', 'Dvdt_Off_Ext1', 'Dvdt_Off_Ext2',
    'Didt_On', 'Didt_On_Fast', 'Dvdt_On', 'Dvdt_On_Fast', 'Icepeak',
    'Ic2', 'VcePeak2', 'Tdoff2', 'Toff2', 'Tf2', 'Didt_Off2',
    'Didt_Off2_Fast2', 'Didt_Off2_Ext1', 'Didt_Off2_Ext2', 'Dvdt_Off2',
    'Dvdt_Off2_Fast2', 'Dvdt_Off2_Ext1', 'Dvdt_Off2_Ext2', 'Eoff2',
    'IF', 'Vce2', 'VcePeak3', 'Irr', 'DiFdt', 'dirrfdt', 'Srr',
    'Dvdt_On2', 'Trr', 'Ta', 'Tb', 'Sf', 'Qrr', 'Erec', 'QRA', 'Qa',
    'Qb', 'Imax', 'Vce3', 'VcePeak4', 'Vge', 'Tsc', 'Didt_Off3', 'Esc',
    'DVX900_DUT_Port_Sel1', 'DVX900_KelvinG2', 'DVX900_KelvinD3',
    'DVX900_KelvinS4', 'DVX900_PreTest1', 'DVX900_TestParam2',
    'DVX900_DVGE', 'DVX900_V_After4', 'DVX900_V_Before5',
    'DVX900_DUT_Port_Sel2', 'DVX900_KelvinG3', 'DVX900_KelvinD4',
    'DVX900_KelvinS5', 'DVX900_PreTest2', 'DVX900_TestParam3',
    'DVX900_DVF', 'DVX900_V_After5', 'DVX900_V_Before6',
    'Kelvin_Zmu_Gate1', 'Kelvin_Zmu_Drain1', 'Kelvin_Zmu_Source1',
    'Zmu_RG1', 'Zmu_Ciss1', 'HV2', 'DC_KELVIN_B1', 'DC_KELVIN_C2',
    'DC_KELVIN_E3', 'IGSS_10V', 'HVP_10V_250uA', 'VTH_250uA',
    'IGSS1_30V', 'ISGS1_30V', 'ICES1_1000V', 'VTH1_1mA',
    'VDSON1_15A_12V', 'VDSON2_15A_15V', 'VDSON3_45A_15V', 'DELAY7',
    'VFEC_15A', 'BVCES1_250uA', 'BVCES2_1mA', 'DELTA_BVCES(2-1)',
    'ICES2_1200V', 'IGSS2_30V', 'ISGS2_30V',
)

EXPECTED_SOURCE_UNITS = (
    'Unit', '', '', '', 'ms', '', 'mA', 'mA', 'mA', 'mA', 'mA', 'V',
    'mA', 'V', 'mA', 'A', 'V', 'V', 'ns', 'ns', 'ns', 'mJ', 'ns',
    'ns', 'ns', 'mJ', 'mJ', 'A/us', 'A/us', 'A/us', 'A/us', 'V/us',
    'V/us', 'V/us', 'V/us', 'A/us', 'A/us', 'V/us', 'V/us', 'A', 'A',
    'V', 'ns', 'ns', 'ns', 'A/us', 'A/us', 'A/us', 'A/us', 'V/us',
    'V/us', 'V/us', 'V/us', 'mJ', 'A', 'V', 'V', 'A', 'A/us', 'A/us',
    '', 'V/us', 'ns', 'ns', 'ns', 'ns', 'uC', 'mJ', '', 'uC', 'uC',
    'A', 'V', 'V', 'V', 'us', 'A/us', 'mJ', '', 'mOhm', 'mOhm',
    'mOhm', 'V', '', 'mV', 'mV', 'mV', '', 'mOhm', 'mOhm', 'mOhm',
    'V', '', 'mV', 'mV', 'mV', 'Ohm', 'Ohm', 'Ohm', 'Ohm', 'pF', 'V',
    'V', 'V', 'V', 'uA', 'V', 'V', 'nA', 'nA', 'uA', 'V', 'V', 'V',
    'V', 'mS', 'V', 'V', 'V', 'V', 'uA', 'nA', 'nA',
)

EXPECTED_COLUMN_COUNT = len(EXPECTED_SOURCE_HEADER)
PARAMETER_START_INDEX = len(SYSTEM_FIELDS)
PARAMETER_FIELDS = EXPECTED_SOURCE_HEADER[PARAMETER_START_INDEX:]
PARAMETER_UNITS = EXPECTED_SOURCE_UNITS[PARAMETER_START_INDEX:]
OUTPUT_PARAMETER_NAMES = tuple(
    f"{field}({unit})" if unit else field
    for field, unit in zip(PARAMETER_FIELDS, PARAMETER_UNITS)
)

assert EXPECTED_COLUMN_COUNT == 123
assert len(EXPECTED_SOURCE_UNITS) == EXPECTED_COLUMN_COUNT
assert len(OUTPUT_PARAMETER_NAMES) == 117
