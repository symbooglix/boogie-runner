// BUG_FOUND
procedure main()
{
        var counter:int;
        var max:int;
        counter := 0;
        assume max > 0;

        while (counter < max)
        {
                assert counter < max;
                counter := counter + 1;
        }

        if ( max > 10 )
        {
                assert counter < 10;
        }
}
