int sra(int a,int b){return a>>b;}
unsigned srl(unsigned a,unsigned b){return a>>b;}
int sll(int a,int b){return a<<b;}
int sra5(int a){return a>>5;}
unsigned srl5(unsigned a){return a>>5;}
int sll5(int a){return a<<5;}
unsigned rotl(unsigned a,unsigned b){return (a<<b)|(a>>(32-b));}
unsigned rotr5(unsigned a){return (a>>5)|(a<<27);}
long long sll64(long long a,int b){return a<<b;}
long long sra64(long long a,int b){return a>>b;}
unsigned long long srl64(unsigned long long a,int b){return a>>b;}
long long sll64i(long long a){return a<<7;}
long long sra64i(long long a){return a>>7;}
unsigned long long srl64i(unsigned long long a){return a>>7;}
long long sra64i40(long long a){return a>>40;}
