#ifndef __SBL_H__
#define __SBL_H__

/*
 * Simple Boot Loader
 * Read, Write, Exec, that's it!
 */

//dependencies
#include <stdint.h>
void sbl_rx8(uint8_t*dat);
void sbl_tx8(uint8_t dat);

//optional dependencies
void sbl_read8(uint8_t*dat, uint32_t addr);
void sbl_write8(uint8_t dat, uint32_t addr);
void sbl_read16(uint16_t*dat, uint32_t addr);
void sbl_write16(uint16_t dat, uint32_t addr);
void sbl_read32(uint32_t*dat, uint32_t addr);
void sbl_write32(uint32_t dat, uint32_t addr);
void sbl_exec(uint32_t addr);


#ifndef SBL_CUSTOM_MEM_ACCESS
void sbl_read8(uint8_t*dat, uint32_t addr)		{*dat = *((uint8_t*)addr);}
void sbl_write8(uint8_t dat, uint32_t addr)		{*((uint8_t*)addr) = dat;}
void sbl_read16(uint16_t*dat, uint32_t addr)	{*dat = *((uint16_t*)addr);}
void sbl_write16(uint16_t dat, uint32_t addr)	{*((uint16_t*)addr) = dat;}
void sbl_read32(uint32_t*dat, uint32_t addr)	{*dat = *((uint32_t*)addr);}
void sbl_write32(uint32_t dat, uint32_t addr)	{*((uint32_t*)addr) = dat;}
#endif

#ifndef SBL_CUSTOM_EXEC
typedef void (*sbl_execfunc_t)(void);
void sbl_exec(uint32_t addr){
	sbl_execfunc_t f = (sbl_execfunc_t)addr;
	f();
}
#endif

//utils, com is always done in little endian
static void sbl_rx(void*dat, unsigned int len){
	uint8_t*dat8 = (uint8_t*)dat;
	for(unsigned int i=0;i<len;i++) sbl_rx8(dat8+i);
}
static void sbl_tx(void*dat, unsigned int len){
	uint8_t*dat8 = (uint8_t*)dat;
	for(unsigned int i=0;i<len;i++) sbl_tx8(*(dat8+i));
}


//COMMANDS (aim at being compatible with ISO7816 T=0 at TPDU level)
#define SBL_CLA 0
#define SBL_INS 1
#define SBL_LEN 4

#define SBL_CMD_CLA_8  	0x08
#define SBL_CMD_CLA_16 	0x10
#define SBL_CMD_CLA_32 	0x20

#define SBL_CMD_INS_READ    0x0A
#define SBL_CMD_INS_WRITE   0x0C
#define SBL_CMD_INS_BASE    0x0B
#define SBL_CMD_INS_EXEC    0x0E

#define SBL_CMD_READ_8		(SBL_CMD_CLA_8  | (SBL_CMD_INS_READ<<8))
#define SBL_CMD_READ_16		(SBL_CMD_CLA_16 | (SBL_CMD_INS_READ<<8))
#define SBL_CMD_READ_32		(SBL_CMD_CLA_32 | (SBL_CMD_INS_READ<<8))

#define SBL_CMD_WRITE_8	 	(SBL_CMD_CLA_8  | (SBL_CMD_INS_WRITE<<8))
#define SBL_CMD_WRITE_16	(SBL_CMD_CLA_16 | (SBL_CMD_INS_WRITE<<8))
#define SBL_CMD_WRITE_32	(SBL_CMD_CLA_32 | (SBL_CMD_INS_WRITE<<8))

#define SBL_CMD_BASE (SBL_CMD_INS_BASE<<8)
#define SBL_CMD_EXEC (SBL_CMD_INS_EXEC<<8)

#define SBL_OK 0x0090
#define SBL_KO 0x0064

static unsigned int compute_len(unsigned int len,unsigned int access_unit){
	switch(access_unit){
	case 16: len = len>>1;break;
	case 32: len = len>>2;break;
	}
	return len;
}

static void sbl_main(void){
	uint32_t base=0;
	uint32_t addr;
	uint16_t cmd;
	uint16_t offset;
	uint8_t len;
	uint16_t status;
	unsigned int access_unit;

	while(1){
		//5 bytes header
		sbl_rx(&cmd,2);
		sbl_rx(&offset,2);
		sbl_rx8(&len);

		addr = base+offset;
		access_unit = cmd & 0xFF;
		len = compute_len(len,access_unit);

		status = SBL_OK;
		switch(cmd){
		case SBL_CMD_READ_8:
		case SBL_CMD_READ_16:
		case SBL_CMD_READ_32:
			sbl_tx8(cmd>>8);//send ISO7816 ACK
			for(unsigned int i=0;i<len;i++){
				uint32_t buf;
				switch(access_unit){
				case 8:
					sbl_read8((uint8_t*)&buf,addr);
					sbl_tx8(buf);
					break;
				case 16:
					sbl_read16((uint16_t*)&buf,addr);
					sbl_tx8(buf);
					sbl_tx8(buf>>8);
					break;
				case 32:
					sbl_read32(&buf,addr);
					sbl_tx8(buf);
					sbl_tx8(buf>>8);
					sbl_tx8(buf>>16);
					sbl_tx8(buf>>24);
					break;
				}
				addr+=access_unit>>3;
			}
			break;
		case SBL_CMD_WRITE_8:
		case SBL_CMD_WRITE_16:
		case SBL_CMD_WRITE_32:
			sbl_tx8(cmd>>8);//send ISO7816 ACK
			for(unsigned int i=0;i<len;i++){
				uint32_t buf;
				uint8_t buf8[4];
				switch(access_unit){
				case 8:
					sbl_rx8(buf8);
					sbl_write8(buf8[0],addr);
					break;
				case 16:
					sbl_rx(buf8,2);
					buf = buf8[1];
					buf = (buf<<8) | buf8[0];
					sbl_write16(buf,addr);
					break;
				case 32:
					sbl_rx(buf8,4);
					buf = buf8[3];
					buf = (buf<<8) | buf8[2];
					buf = (buf<<8) | buf8[1];
					buf = (buf<<8) | buf8[0];
					sbl_write32(buf,addr);
					break;
				}
				addr+=access_unit>>3;
			}
			break;
		case SBL_CMD_BASE:
			if(4==len){
				sbl_tx8(cmd>>8);//send ISO7816 ACK
				uint8_t buf[4];
				sbl_rx(buf,4);
				base = buf[3];
				base = (base<<8) | buf[2];
				base = (base<<8) | buf[1];
				base = (base<<8) | buf[0];
			}else{
				status = SBL_KO;
			}
			break;
		case SBL_CMD_EXEC:
			sbl_exec(addr);
			break;
		default:
			status = SBL_KO;
		}
		sbl_tx(&status,2);
	}
}

#endif
