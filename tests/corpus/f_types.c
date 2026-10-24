enum E { E0, E1 };
struct Max { long long a; long double b; void *p; };
struct Def { char c; } __attribute__((aligned));
struct A64 { char c; } __attribute__((aligned(64)));
int sz_char(void) { return sizeof(char); }
int al_char(void) { return __alignof__(char); }
int sz_short(void) { return sizeof(short); }
int al_short(void) { return __alignof__(short); }
int sz_int(void) { return sizeof(int); }
int al_int(void) { return __alignof__(int); }
int sz_long(void) { return sizeof(long); }
int al_long(void) { return __alignof__(long); }
int sz_ll(void) { return sizeof(long long); }
int al_ll(void) { return __alignof__(long long); }
int sz_ptr(void) { return sizeof(void *); }
int al_ptr(void) { return __alignof__(void *); }
int sz_float(void) { return sizeof(float); }
int al_float(void) { return __alignof__(float); }
int sz_double(void) { return sizeof(double); }
int al_double(void) { return __alignof__(double); }
int sz_ldouble(void) { return sizeof(long double); }
int al_ldouble(void) { return __alignof__(long double); }
int sz_bool(void) { return sizeof(_Bool); }
int al_bool(void) { return __alignof__(_Bool); }
int sz_enum(void) { return sizeof(enum E); }
int al_enum(void) { return __alignof__(enum E); }
int sz_wchar(void) { return sizeof(__WCHAR_TYPE__); }
int al_wchar(void) { return __alignof__(__WCHAR_TYPE__); }
int sz_max(void) { return sizeof(struct Max); }
int al_max(void) { return __alignof__(struct Max); }
int sz_defalign(void) { return sizeof(struct Def); }
int al_defalign(void) { return __alignof__(struct Def); }
int sz_align64(void) { return sizeof(struct A64); }
int al_align64(void) { return __alignof__(struct A64); }
int char_signed(void) { return (char)-1 < 0; }
int wchar_signed(void) { return (__WCHAR_TYPE__)-1 < 0; }
int biggest(void) { return __BIGGEST_ALIGNMENT__; }
int endian(void) { unsigned x=0x12345678; return *(unsigned char *)&x; }
int float_repr(void) { union {float f; unsigned u;} x={1.0f}; return x.u; }
long long double_repr(void) { union {double d; long long u;} x={1.0}; return x.u; }
int sz_iptr(void) { return sizeof(int *); }
int al_iptr(void) { return __alignof__(int *); }
int sz_fptr(void) { return sizeof(int (*)(int)); }
int al_fptr(void) { return __alignof__(int (*)(int)); }
struct Limit { char c; } __attribute__((aligned(268435456)));
int largest(void) { return __alignof__(struct Limit); }
