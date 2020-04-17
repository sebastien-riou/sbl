#!/usr/bin/env python3

import serial
from intelhex import IntelHex
import sys, os

class SBL(object):
    @staticmethod
    def hexstr(bytes, head="", separator=" ", tail=""):
        """Returns an hex string representing bytes
        @param bytes:  a list of bytes to stringify,
                    e.g. [59, 22, 148, 32, 2, 1, 0, 0, 13]
                    or a bytearray
        @param head: the string you want in front of each bytes. Empty by default.
        @param separator: the string you want between each bytes. One space by default.
        @param tail: the string you want after each bytes. Empty by default.
        """
        if bytes is not bytearray:
            bytes = bytearray(bytes)
        if (bytes is None) or bytes == []:
            return ""
        else:
            pformat = head+"%-0.2X"+tail
            return (separator.join(map(lambda a: pformat % ((a + 256) % 256), bytes))).rstrip()

    @staticmethod
    def int_to_ba(x, width=-1, byteorder='little'):
        if width<0:
            width = max(1,(x.bit_length() + 7) // 8)
        b = x.to_bytes(width, byteorder)
        return bytearray(b)

    @staticmethod
    def to_int(ba, byteorder='little'):
        b = bytes(ba)
        return int.from_bytes(b, byteorder)

    @staticmethod
    def ba(hexstr_or_int,width=-1):
        """Extract hex numbers from a string and returns them as a bytearray
        It also handles int and list of int as argument
        If it cannot convert, it raises ValueError
        """
        try:
            t1 = hexstr_or_int.lower()
            t2 = "".join([c if c.isalnum() else " " for c in t1])
            t3 = t2.split(" ")
            out = bytearray()
            for bstr in t3:
                if bstr != "":
                    l = len(bstr)
                    if(l % 2):
                        bstr = "0"+bstr
                        l+=1
                    for p in range(0,l,2):
                        s=bstr[p:p+2]
                        out.extend((bytearray.fromhex(s)))
        except:
            #seems arg is not a string, assume it is a int
            try:
                out = SBL.int_to_ba(hexstr_or_int,width)
            except:
                # seems arg is not an int, assume it is a list
                try:
                    #print(hexstr_or_int, " not a string nor an int")
                    out = bytearray(hexstr_or_int)
                except:
                    raise ValueError()
        return out

    @staticmethod
    def sbl_cmd(ser,apdu,waitack=True,waitstatus=True,verbose=False):
        if apdu is not bytes:
            apdu = SBL.ba(apdu)
        out = bytearray()
        header=apdu[0:5]
        ser.write(header)
        if verbose:
            print(">>>",SBL.hexstr(header),flush=True)
        if waitack:
            #print("wait ack")
            ack=ser.read()
            if verbose:
                print("  <",SBL.hexstr(ack),flush=True)
            expected_ack=SBL.ba(apdu[1])
            if ack!=expected_ack:
                print("ERROR ACK=",SBL.hexstr(ack), "expected ACK=",SBL.hexstr(expected_ack))
                ser.timeout = 0.1
                sw2=ser.read()
                ser.timeout = None
                print("SW2=",SBL.hexstr(sw2))
                raise ValueError()
            if len(apdu)>5:
                data=apdu[5:]
                ser.write(data)
                if verbose:
                    print(" >>",SBL.hexstr(data),flush=True)
            elif apdu[4]>0:
                out += ser.read(apdu[4])
                if verbose:
                    print(" <<",SBL.hexstr(out),flush=True)
            if waitstatus:
                status = ser.read(2)
                if verbose:
                    print("  <",SBL.hexstr(status),flush=True)
                if status!=bytes(SBL.ba("90 00")):
                    print("ser.timeout=",ser.timeout)
                    print(SBL.hexstr(ack))
                    print(SBL.hexstr(out))
                    print(SBL.hexstr(status))
                    raise ValueError()
        
        return out

    @staticmethod
    def sbl_set_base(ser,base,verbose=False):
        cmd=SBL.ba("00 0B 00 00 04") + SBL.ba(base,4)
        SBL.sbl_cmd(ser,cmd,verbose=verbose)

    @staticmethod
    def sbl_exec(ser,offset,data=None,rxsize=0,waitack=True,waitstatus=True,verbose=False):
        cmd=SBL.ba("00 0E") + SBL.int_to_ba(offset, width=2)
        if data is not None:
            assert(len(data)<=255)
            assert(rxsize==0)
            if len(data)>0:
                cmd+=SBL.int_to_ba(len(data))
                cmd+=data
        else:
            assert(rxsize<=255)
            cmd+=SBL.ba(rxsize)
        if len(cmd)<5:
            cmd+=SBL.ba("00")
        return SBL.sbl_cmd(ser,cmd,waitack,waitstatus,verbose=verbose)

    @staticmethod
    def sbl_read(ser,size=1,offset=0,access_width=8,loop_size=252,verbose=False):
        assert(access_width in [8,16,32])
        assert(loop_size<=255)
        assert(0==(loop_size%(access_width//8)))
        loops = size // loop_size
        out=bytearray()
        for i in range(0,loops):
            out+=SBL.sbl_cmd(ser,SBL.ba(access_width) +SBL.ba("0A") + SBL.int_to_ba(offset, width=2)+ SBL.ba(loop_size),verbose=verbose)
            offset+=loop_size
            size-=loop_size
        if size>0:
            out+=SBL.sbl_cmd(ser,SBL.ba(access_width) +SBL.ba("0A") + SBL.int_to_ba(offset, width=2)+ SBL.ba(size),verbose=verbose)
        return out

    @staticmethod
    def sbl_write(ser,data,offset=0,access_width=8,loop_size=252,verbose=False):
        assert(access_width in [8,16,32])
        assert(loop_size<=255)
        assert(0==(loop_size%(access_width//8)))
        size=len(data)
        loops = size // loop_size
        datoffset=0
        for i in range(0,loops):
            SBL.sbl_cmd(ser,SBL.ba(access_width) +SBL.ba("0C") + SBL.int_to_ba(offset, width=2)+ SBL.ba(loop_size) + data[datoffset:datoffset+loop_size],verbose=verbose)
            offset+=loop_size
            datoffset+=loop_size
            size-=loop_size
        if size>0:
            SBL.sbl_cmd(ser,SBL.ba(access_width) +SBL.ba("0C") + SBL.int_to_ba(offset, width=2)+ SBL.ba(size)+ data[datoffset:],verbose=verbose)

    @staticmethod
    def format_mem_dump(base,dat,unit=1,upl=16,fill='0',byteorder='little'):
        r=len(dat)
        j=0
        out=""
        width=unit*2
        while r>0:
            out += "%08x: "%(base+j*unit*upl)
            for i in range(0,upl):
                offset=j*upl+i*unit
                u = dat[offset:offset+unit] 
                val = int.from_bytes(u,byteorder=byteorder)
                out += f'{val:{fill}{width}x} '
                r-=1
                if 0==r:
                    break
            out += '\n'
            j+=1
        return out

    @staticmethod
    def sbl_sync(ser):
        ser.reset_input_buffer()
        status=SBL.ba("00 00")
        while status!=SBL.ba("64 00"):
            status = bytearray()
            while len(status) <2:
                ser.write(SBL.ba("00"))
                ser.timeout = 0.1
                tmp = ser.read(2)
                ser.timeout = None
                status += tmp
            #print(SBL.hexstr(status), flush=True)

    def __init__(self,ser,verbose=False):
        self.ser=ser
        self.base=None
        self.verbose=verbose
        SBL.sbl_sync(ser)

    def _set_base(self,address):
        offset = address & 0xFFFF
        base=address - offset
        assert(base<=0xFFFF0000)
        if self.base != base:
            self.sbl_set_base(self.ser,base,verbose=self.verbose)
            self.base=base
        return offset

    def read(self,size=1,address=0,access_width=8,loop_size=252):
        offset=self._set_base(address)
        return self.sbl_read(self.ser,size,offset,access_width,loop_size,verbose=self.verbose)

    def write(self,data,address=0,access_width=8,loop_size=252):
        offset=self._set_base(address)
        if data is not bytes:
            data=SBL.ba(data)
        return self.sbl_write(self.ser,data,offset,access_width,loop_size,verbose=self.verbose)

    def fill(self,val,size=1,address=0,access_width=8,loop_size=252):
        offset=self._set_base(address)
        valbytes=self.ba(val)
        vallen=len(valbytes)
        n=size // vallen
        dat = valbytes * n
        self.sbl_write(self.ser,dat[:size],offset,access_width,loop_size,verbose=self.verbose)

    def load_ihex(self,ihex,offset=0,access_width=8,loop_size=252):
        all_sections = ihex.segments()
        print("input hex file sections:")
        for sec in all_sections:
            print("0x%08X 0x%08X"%(sec[0],sec[1]-1))
        for sec in all_sections:
            dat=bytearray()
            for i in range(sec[0],sec[1]):
                dat.append(ihex[i])
            self.write(dat,address=sec[0]+offset)

    def verify_ihex(self,ihex,offset=0,access_width=8,loop_size=252):
        all_sections = ihex.segments()
        print("input hex file sections:")
        for sec in all_sections:
            print("0x%08X 0x%08X"%(sec[0],sec[1]-1))
        for sec in all_sections:
            dat=bytearray()
            for i in range(sec[0],sec[1]):
                dat.append(ihex[i])
            device_dat=self.read(len(dat),address=sec[0]+offset)
            assert(dat==device_dat)

    def exec(self,address,data=None,rxsize=0,waitack=True,waitstatus=True):
        offset=self._set_base(address)
        return self.sbl_exec(self.ser,offset,data,rxsize,waitack=waitack,waitstatus=waitstatus)
        
    def write_int(self,data,addr,size=4,access_width=32):
        return self.write(data=data.to_bytes(size,byteorder='little'),address=addr,access_width=access_width)

    def write_int16(self,data,addr):
        return self.write_int(data,addr=addr,size=2,access_width=16)

    def write_int32(self,data,addr):
        return self.write_int(data,addr=addr,size=4,access_width=32)

    def read_int(self,addr,size=4,access_width=32):
        b=self.read(size=size,address=addr,access_width=access_width)
        return int.from_bytes(b,byteorder='little')

    def read_int16(self,addr):
        return self.read_int(addr,size=2,access_width=16)
        
    def read_int32(self,addr):
        return self.read_int(addr,size=4,access_width=32)

    def dump_int16(self,addr):
        val=self.read_int16(addr)
        print("int@0x%x = 0x%08x"%(addr,val))
        return val

    def dump_int32(self,addr):
        val=self.read_int32(addr)
        print("int@0x%x = 0x%08x"%(addr,val))
        return val
    
    def dump_mem(self,addr=0,size=16,access_width=8,loop_size=252,unit=1,upl=16,fill='0',byteorder='little'):
        dat=self.read(size=size,address=addr,access_width=access_width,loop_size=loop_size)
        s=self.format_mem_dump(base=addr,dat=dat,unit=unit,upl=upl,fill=fill,byteorder=byteorder)
        print(s)
        return dat
        


def sbl_demo_main():
    args_min=2
    args_max=2
    if (len(sys.argv) > (args_max+1) ) | (len(sys.argv) < (args_min+1)) :
        print("ERROR: incorrect arguments")
        print("Usage:")
        print("name <device> <ihex file>")
        exit()


    device = sys.argv[1]
    ihexf = sys.argv[2]

    ser = serial.Serial(device, baudrate=115200, exclusive=True)
    ser.reset_input_buffer()
    #print(SBL.hexstr(ser.read(215)))
    sbl=SBL(ser)
    ih = IntelHex()
    ih.loadhex(ihexf)
    sbl.load_ihex(ih)
    sbl.verify_ihex(ih)


    #append the start address info on 4 bytes, little endian
    if ih.start_addr is None:
        print("ERROR: no start address defined in the hex file")
        exit(-1)

    try:
        start=ih.start_addr['EIP']
    except:
        start=ih.start_addr['IP']+(ih.start_addr['CS']<<4)
    #print(ih.start_addr)
    #print("start=0x%08x"%start)

    print(SBL.hexstr(sbl.exec(address=start,rxsize=32,waitack=False)))

    sys.stdout.flush()

if __name__ == "__main__":
    sbl_demo_main()
