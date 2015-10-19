// FULLY_EXPLORED
function {:builtin "div"} doDiv(int, int) returns (int);

procedure main()
{
    assert (forall x:int, y:int :: x div y == doDiv(x, y) );
}
