#!/usr/bin/env python
import sys
sys.path.append("..")

from comms import *
import serial
import time
import pickle
import pprint
import argparse

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Calibrate the encoder on a motor controller board.')
    parser.add_argument('serial', type=str, help='Serial port')
    parser.add_argument('--baud_rate', type=int, help='Serial baud rate')
    parser.add_argument('board_id', type=int, help='Board ID')
    parser.add_argument('duty_cycle', type=float, help='Duty cycle')
    parser.add_argument('file_name', type=str, help='File name to record data')
    parser.add_argument('--steps', type=int, help='Number of steps')
    parser.add_argument('--delay', type=float, help='Delay between steps')
    parser.set_defaults(baud_rate=COMM_DEFAULT_BAUD_RATE, duty_cycle=0.6, steps=50, delay=0.1, file_name='')
    args = parser.parse_args()

    #
    # Data collection
    #

    ser = serial.Serial(port=args.serial, baudrate=args.baud_rate, timeout=0.5)
    time.sleep(0.1)

    client = BLDCControllerClient(ser)
    """
    client.enterBootloader([args.board_id])
    time.sleep(0.2)
    try:
        print (client.enumerateBoards([args.board_id]))
    except:
        print("Failed to receive enumerate response")
    time.sleep(0.2)

    client.leaveBootloader([args.board_id])
    time.sleep(0.2) # Wait for the controller to reset
    ser.reset_input_buffer()
    """
    ##### CALIBRATION CODE ######
    """
    calibration_obj = client.readCalibration([args.board_id])
    
    client.setZeroAngle([args.board_id], [calibration_obj['angle']])
    client.setInvertPhases([args.board_id], [calibration_obj['inv']])
    client.setERevsPerMRev([args.board_id], [calibration_obj['epm']])
    client.setTorqueConstant([args.board_id], [calibration_obj['torque']])
    client.setPositionOffset([args.board_id], [calibration_obj['zero']])
    if 'eac_type' in calibration_obj and calibration_obj['eac_type'] == 'int8':
        print('EAC calibration available')
        try:
            client.writeRegisters([args.board_id], [0x1100], [1], [struct.pack('<f', calibration_obj['eac_scale'])])
            client.writeRegisters([args.board_id], [0x1101], [1], [struct.pack('<f', calibration_obj['eac_offset'])])
            eac_table_len = len(calibration_obj['eac_table'])
            slice_len = 64
            for i in range(0, eac_table_len, slice_len):
                table_slice = calibration_obj['eac_table'][i:i+slice_len]
                client.writeRegisters([args.board_id], [0x1200+i], [len(table_slice)], [struct.pack('<{}b'.format(len(table_slice)), *table_slice)])
        except ProtocolError:
            print('WARNING: Motor driver board does not support encoder angle compensation, try updating the firmware.')
    client.setCurrentControlMode([args.board_id])
    client.writeRegisters([args.board_id], [0x1030], [1], [struct.pack('<H', 1000)])
    # print("Motor %d ready: supply voltage=%fV", args.board_id, client.getVoltage(args.board_id))
    
    # Setting gains for motor
    client.writeRegisters([args.board_id], [0x1003], [1], [struct.pack('<f', 1)])  # DI Kp
    client.writeRegisters([args.board_id], [0x1004], [1], [struct.pack('<f', 0)]) # DI Ki
    client.writeRegisters([args.board_id], [0x1005], [1], [struct.pack('<f', 1)])  # QI Kp
    client.writeRegisters([args.board_id], [0x1006], [1], [struct.pack('<f', 0)]) # QI Ki
    
    
    client.writeRegisters([args.board_id], [0x2006], [1], [struct.pack('<f', args.duty_cycle)])
    client.writeRegisters([args.board_id], [0x2000], [1], [struct.pack('<B', 2)]) # Torque control
    """
    ##### END CALIBRATION CODE ######
    client.writeRegisters([args.board_id], [0x2000], [1], [struct.pack('<B', 6)])  # Open Loop Spin Control
    
    # The number of values returned by the recorder (all floats)
    num_recorder_elements = 11
    
    reset = struct.unpack('<B', client.readRegisters([args.board_id], [0x300b], [1])[0])[0]
    print("reset: %u" % reset)
    success = struct.unpack('<B', client.readRegisters([args.board_id], [0x3009], [1])[0])[0]
    print("started: %u" % success)
    
    time.sleep(1.2)

    while 1:
        l = struct.unpack('<H', client.readRegisters([args.board_id], [0x300a], [1])[0])[0]
        if l != 0:
            break
        time.sleep(0.1)

    # Reset the command mode so we're not still spinning/burning current
    client.writeRegisters([args.board_id], [0x2000], [1], [struct.pack('<B', 1)])  # Set control mode to raw phase current

    arr = []
    for i in range(0, l, num_recorder_elements):
        # Grab the recorder data
        regval = client.readRegisters([args.board_id], [0x8000 + i], [num_recorder_elements])
        if not regval[0]:
            print("Skipping %u"%i)
            continue
        a = (struct.unpack("<" + str(num_recorder_elements) + "f", regval[0]))
        arr += [a]

    print("Array has %u elements"%len(arr))
    print("Array[0]: ",arr[0])
    
    if args.file_name:
        with open(args.file_name, 'wb+') as file:
            pickle.dump(arr, file)
        print("dumped data to file " + args.file_name)
    else:
        pp = pprint.PrettyPrinter()
        pp.pprint(arr[0])
