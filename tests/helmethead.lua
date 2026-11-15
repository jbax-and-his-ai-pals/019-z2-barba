-- Palace 2 Helmethead: fireball-only kill (no thrust techniques), key drop, scroll unlock and exit.
-- His floating helmets ($22 in this world) count as boss parts so the driver doesn't clear them.
dofile(TEST_DIR..'/boss_fight.lua')
runBossFight{name='helmethead',world=3,region=0,number=2,room=0x22,page=0,kind=3,
    bosses={[0x21]=true,[0x22]=true},final=0x21,attack=4,frames=12000,exitPage=3,
    checks=function(check,fight)
        check((fight.damage[0x21] or 0)>0,'fireballs damaged Helmethead ($21)')
    end}
