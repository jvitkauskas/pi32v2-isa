unsigned rl5(unsigned a){return (a<<5)|(a>>27);}
unsigned rl1(unsigned a){return (a<<1)|(a>>31);}
unsigned rr1(unsigned a){return (a>>1)|(a<<31);}
unsigned long long rl64(unsigned long long a){return (a<<5)|(a>>59);}
unsigned long long rr64(unsigned long long a,unsigned n){return (a>>n)|(a<<(64-n));}
unsigned rrv(unsigned a,unsigned n){return (a>>n)|(a<<(32-n));}
unsigned rotm(unsigned a,unsigned n){return (a>>(n&31))|(a<<((-n)&31));}
