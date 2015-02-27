// FULLY_EXPLORED
function {:builtin "rem"} doRem(int, int) returns (int);

function doRem2(x:int, y:int) returns(int)
{
    if y < 0 then (- (x mod y)) else (x mod y)
}

procedure main()
{
    assert (forall x:int, y:int :: doRem2(x, y) == doRem(x, y) );
}
