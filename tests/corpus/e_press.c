extern void use(int,int,int,int,int,int,int,int,int,int,int,int);
void press(int *p){
  int a0=p[0],a1=p[1],a2=p[2],a3=p[3],a4=p[4],a5=p[5],a6=p[6],a7=p[7],a8=p[8],a9=p[9],a10=p[10],a11=p[11];
  int s=a0<<3, t=a1>>2, u=(unsigned)a2>>5, v=a3<<a4, w=a5>>a6, x=(unsigned)a7>>a8, y=a9*a10, z=a11&a0;
  use(a0+s,a1+t,a2+u,a3+v,a4+w,a5+x,a6+y,a7+z,a8^a9,a9|a10,a10-a11,a11+a0);
  p[0]=s+t+u+v+w+x+y+z+a0+a1+a2+a3+a4+a5+a6+a7+a8+a9+a10+a11;
}
