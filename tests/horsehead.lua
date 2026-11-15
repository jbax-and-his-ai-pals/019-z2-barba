-- Palace 1 Horsehead: fireball-only kill (no thrust techniques), key drop, scroll unlock and exit.
dofile(TEST_DIR..'/boss_fight.lua')
runBossFight{name='horsehead',world=3,region=0,number=1,room=0x0D,page=0,kind=3,
    bosses={[0x20]=true},final=0x20,attack=3,frames=12000,exitPage=3,
    checks=function(check,fight)
        check((fight.damage[0x20] or 0)>0,'fireballs damaged Horsehead ($20)')
    end}
