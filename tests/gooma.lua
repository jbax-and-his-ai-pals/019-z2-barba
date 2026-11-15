-- Palace 5 Gooma: fireball-only kill (no thrust techniques), key drop, scroll unlock and exit.
dofile(TEST_DIR..'/boss_fight.lua')
runBossFight{name='gooma',world=3,region=2,number=5,room=0x29,page=0,kind=3,
    bosses={[0x21]=true},final=0x21,attack=6,frames=12000,exitPage=3,
    checks=function(check,fight)
        check((fight.damage[0x21] or 0)>0,'fireballs damaged Gooma ($21)')
    end}
