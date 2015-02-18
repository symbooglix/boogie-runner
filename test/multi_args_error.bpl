// BUG_FOUND
var g:int;
var h:int;
procedure main(a:int, b:int, c:int, d:[int]int)
{
    assert a + b + c + d[c] > 5 + g - h;
}
