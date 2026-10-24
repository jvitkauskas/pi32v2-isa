typedef long long s64;
int k1(void){return __builtin_pi32v2_clz(1);}
int k2(void){return __builtin_pi32v2_cls(5);}
int k3(void){return __builtin_pi32v2_cls(-6);}
int k4(void){return __builtin_pi32v2_popcount(0xff);}
int k5(void){return __builtin_pi32v2_rev8(0x12345678);}
int k6(void){return __builtin_pi32v2_zcmp(0);}
int k7(void){return __builtin_pi32v2_zcmp(0x12);}
int k8(void){return __builtin_pi32v2_uextra(0x12345678,8,8);}
int k9(void){return __builtin_pi32v2_sextra(0x12348678,8,8);}
int k10(void){return __builtin_pi32v2_clz(0);}
int k11(void){return __builtin_pi32v2_cls(0);}
int k12(int a){return __builtin_pi32v2_zcmp(a)==0;}
int k13(int a){return __builtin_pi32v2_zcmp(a)&1;}
int k14(int a){ return __builtin_pi32v2_clz(a)>32;}
int k15(int a){ return __builtin_pi32v2_cls(a)>31;}
