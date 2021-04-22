import yaml
from os import path

lookup_wafer_tsmc_rd53 = {
    'N25A67-01B6': 16,
    'N25A67-02B1': 17,
    'N25A67-03A4': 18,
    'N25A67-04H2': 19,
    'N25A67-05G5': 20,
    'N25A67-06G0': 21,
    'N25A67-07F3': 22,
    'N25A67-08E6': 23,
    'N25A67-09E1': 24,
    'N25A67-10E6': 25,
    'N25A67-12D4': 27,
    'N25A67-13C7': 28,
    'N25A67-14C2': 29,
    'N25A67-15B5': 30,
    'N25A67-16B8': 31,
    'N25A67-17A3': 32,
    'N25A67-18H1': 33,
    'N25A67-19G4': 34,
    'N25A67-20H1': 35,
    'N25A67-21G4': 36,
    'N25A67-22F7': 37,
    'N25A67-23F2': 38,
    'N25A67-24E5': 39,
    'N25A67-25E8': 40,
    'N2GW02-01C4': 48,
    'N2GW02-02XX': 49,
    'N2GW02-03XX': 50,
    'N2GW02-04XX': 51,
    'N2GW02-05XX': 52,
    'N2GW02-06G6': 53,
    'N2GW02-07G1': 54,
    'N2GW02-08F4': 55,
    'N2GW02-09E7': 56,
    'N2GW02-10F4': 57,
    'N2GW02-11E7': 58,
    'N2GW02-12E2': 59,
    'N2GW02-13D5': 60,
    'N2GW02-14D0': 61,
    'N2GW02-15C3': 62,
    'N2GW02-16XX': 63,
    'N2GW02-17XX': 64,
    'N2GW02-18A4': 65,
    'N2GW02-19H2': 66,
    'N2GW02-20A4': 67,
    'N2GW02-21H1': 68,
    'N2GW02-22G5': 69,
    'N2GW02-23G0': 70,
    'N2GW02-24XX': 71,
    'N2WX39-01G0': 80,
    'N2WX39-02F3': 81,
    'N2WX39-03E6': 82,
    'N2WX39-04E1': 83,
    'N2WX39-05D4': 84,
    'N2WX39-06C7': 85,
    'N2WX39-07C2': 86,
    'N2WX39-08B5': 87,
    'N2WX39-09B0': 88,
    'N2WX39-10B5': 89,
    'N34U61-01D2': 112,
    'N34U61-02C5': 113,
    'N34U61-03C0': 114,
    'N34U61-04B3': 115,
    'N34U61-05A6': 116,
    'N34U61-06A1': 117,
    'N34U61-07G7': 118,
    'N34U61-08G2': 119,
    'N34U61-09F5': 120,
    'N34U61-10G2': 121,
    'N34U61-11F5': 122,
    'N34U61-12F0': 123,
    'N34U61-13E3': 124,
    'N34U61-14D6': 125,
    'N34U61-15D1': 126,
    'N34U61-16C4': 127,
    'N34U61-17B7': 128,
    'N34U61-18B2': 129,
    'N34U61-19A5': 130,
    'N34U61-20B2': 131,
    'N34U61-21A5': 132,
    'N34U61-22A0': 133,
    'N34U61-23G6': 134,
    'N34U61-24G1': 135,
    'N34U61-25F4': 136
}


def parse_wafer_sn(sn):
    all_lookups = {}
    if sn[0].lower() == 'n' and len(sn) == 11:
        for tsmc_sn in lookup_wafer_tsmc_rd53.keys():
            if sn.lower()[:-2] in tsmc_sn.lower():
                return tsmc_sn
        else:
            raise ValueError(f'Unknown serial number: {sn}')
    else:
        for d in lookup_tables.values():
            for k, v in d.items():
                all_lookups[k] = v
        for identifier, tsmc_sn in all_lookups.items():
            if sn in identifier:
                return tsmc_sn
        else:
            raise ValueError(f'Unknown serial number: {sn}')


def generate_itk_chip_sn(rd53_chip_sn):
    return '20UPGFC{0:07d}'.format(int(rd53_chip_sn, 16))


def generate_itk_wafer_sn(rd53_wafer_no):
    return '20UPGFW{0:07d}'.format(rd53_wafer_no)


def find_wafer_from_chip_sn(chip_sn):
    if '0x' in chip_sn and len(chip_sn) == 6:   # RD53 SN
        wafer_no_rd53 = int(chip_sn[2:4], 16)
    elif '20UPGFC' in chip_sn:  # ITk SN
        wafer_no_rd53 = int(str(hex(int(chip_sn[-7:])))[2:4], 16)
    else:
        raise ValueError(f'Invalid SN: {chip_sn}')

    return wafer_no_rd53


def find_chip(chip_sn):
    if '0x' in chip_sn and len(chip_sn) == 6:   # RD53 SN
        col = int(chip_sn[4:5], 16)
        row = int(chip_sn[5:6], 16)
    elif '20UPGFC' in chip_sn:  # ITk SN
        wafer_no_rd53 = str(hex(int(chip_sn[-7:])))
        col = int(wafer_no_rd53[4:5], 16)
        row = int(wafer_no_rd53[5:6], 16)
    else:
        raise ValueError(f'Invalid SN: {chip_sn}')

    return col, row


def _input_options(text, options):
    print(text)
    for i in range(len(options)):
        print(str(i + 1) + ":", options[i])

    inp = int(input(f'\nPlease choose an option [1-{i + 1}]: '))
    if inp in range(1, len(options) + 1):
        return inp - 1
    else:
        raise ValueError('Invalid input!')


if __name__ == '__main__':

    lookup_file = path.join(path.dirname(path.abspath(__file__)), 'flipchip_lookup.yaml')
    with open(lookup_file, 'r') as f:
        lookup_tables = yaml.load(f)

    option = _input_options('What information do you have available?', ['Chip serial number (any format)', 'Wafer number (any format)', ''])

    if option == 0:   # Chip SN
        print('Accepted serial number formats:')
        print('ATLAS / ITk : 20UPGFCXXXXXXX')
        print('RD53        : 0xWWCR')
        sn = input('\nEnter chip serial number: ')
        wafer_no_rd53 = find_wafer_from_chip_sn(sn)
        col, row = find_chip(sn)

        wafer_sn_tsmc = next(key for key, value in lookup_wafer_tsmc_rd53.items() if value == wafer_no_rd53)
        wafer_sn_itk = generate_itk_wafer_sn(wafer_no_rd53)

        print(' ')
        print(f'{sn} is a chip from wafer {wafer_sn_itk} (ITk) / {wafer_no_rd53} (RD53) / {wafer_sn_tsmc} (TSMC).')
        print(f'Alternate notation for chip {sn}: Wafer {wafer_no_rd53}, Chip {col}-{row}')

    elif option == 1:  # Wafer SN
        print('Accepted serial number formats:')
        print('ATLAS / ITk : 20UPGFWXXXXXXX')
        print('RD53        : XX / XXX')
        print('TSMC        : NXXXXX-XXXX')
        print('Other       : e.g. W6')
        sn = input('\nEnter wafer number: ')
        wafer_sn_tsmc = parse_wafer_sn(sn)

        wafer_no_rd53 = lookup_wafer_tsmc_rd53[wafer_sn_tsmc]
        wafer_sn_itk = generate_itk_wafer_sn(wafer_no_rd53)

        print(' ')
        print(f'Wafer {sn} is called {wafer_sn_itk} (ITk) / {wafer_no_rd53} (RD53) / {wafer_sn_tsmc} (TSMC).')
