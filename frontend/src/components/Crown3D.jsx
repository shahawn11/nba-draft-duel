// Photoreal 3D crown (Three.js): an ornate king's crown -- a flared gold band
// jeweled with refractive red/green/blue/white gems, pearl-beaded top & bottom
// rims, and rounded prong points topped with gold ball finials. Lit by a studio
// environment (RoomEnvironment) for real metallic reflections, viewed nearly
// head-on (slightly from below) and spinning a full 360deg. Rendered to a small
// transparent canvas behind the GOAT card content.
import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js'

const W = 104
const H = 92

export default function Crown3D() {
  const mountRef = useRef(null)
  useEffect(() => {
    const mount = mountRef.current
    if (!mount) return
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'low-power' })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
    renderer.setSize(W, H)
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure = 1.15
    mount.appendChild(renderer.domElement)

    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(32, W / H, 0.1, 100)
    camera.position.set(0, 0.18, 4.8)   // nearly head-on, a touch below
    camera.lookAt(0, 0.32, 0)

    const pmrem = new THREE.PMREMGenerator(renderer)
    const envTex = pmrem.fromScene(new RoomEnvironment(), 0.04).texture
    scene.environment = envTex

    const junk = []                       // geometries + materials to dispose
    const keep = (x) => { junk.push(x); return x }

    const gold = keep(new THREE.MeshStandardMaterial({ color: 0xffc833, metalness: 1.0, roughness: 0.22, envMapIntensity: 1.4 }))
    const pearl = keep(new THREE.MeshPhysicalMaterial({
      color: 0xfff6ea, metalness: 0.0, roughness: 0.22, clearcoat: 1, clearcoatRoughness: 0.2,
      iridescence: 0.5, iridescenceIOR: 1.3, envMapIntensity: 1.2,
    }))
    const gemMat = (c) => keep(new THREE.MeshPhysicalMaterial({
      color: c, metalness: 0.0, roughness: 0.05, transmission: 0.92, ior: 2.2, thickness: 0.5,
      attenuationColor: new THREE.Color(c), attenuationDistance: 0.5, envMapIntensity: 1.6, specularIntensity: 1.0,
    }))

    // shared geometries (reused across the many beads/points)
    const gPearlSm = keep(new THREE.SphereGeometry(0.042, 14, 14))
    const gPearlBig = keep(new THREE.SphereGeometry(0.05, 16, 16))
    const gFinial = keep(new THREE.SphereGeometry(0.1, 20, 20))
    const gProng = keep(new THREE.CylinderGeometry(0.05, 0.1, 0.6, 20))
    const gGem = keep(new THREE.IcosahedronGeometry(0.13, 0))

    const crown = new THREE.Group()

    // flared gold band + thick bottom rim + thinner top rim
    crown.add(new THREE.Mesh(keep(new THREE.CylinderGeometry(1.04, 0.92, 0.95, 80, 1, true)), gold))
    const rimBot = new THREE.Mesh(keep(new THREE.TorusGeometry(0.95, 0.085, 22, 90)), gold)
    rimBot.rotation.x = Math.PI / 2; rimBot.position.y = -0.47; crown.add(rimBot)
    const rimTop = new THREE.Mesh(keep(new THREE.TorusGeometry(1.03, 0.05, 22, 90)), gold)
    rimTop.rotation.x = Math.PI / 2; rimTop.position.y = 0.47; crown.add(rimTop)

    // pearl beading along both rims
    const PEARLS = 34
    for (let i = 0; i < PEARLS; i++) {
      const a = (i / PEARLS) * Math.PI * 2, x = Math.cos(a), z = Math.sin(a)
      const top = new THREE.Mesh(gPearlSm, pearl); top.position.set(x * 1.03, 0.47, z * 1.03); crown.add(top)
      const bot = new THREE.Mesh(gPearlBig, pearl); bot.position.set(x * 0.95, -0.47, z * 0.95); crown.add(bot)
    }

    // large jewels set into the band face (ruby / emerald / sapphire / diamond)
    const gemColors = [0xd11a2a, 0x1aa34a, 0x2a5bd1, 0xeaf4ff, 0xd11a2a, 0x1aa34a]
    gemColors.forEach((c, i) => {
      const a = (i / gemColors.length) * Math.PI * 2, x = Math.cos(a), z = Math.sin(a)
      const gem = new THREE.Mesh(gGem, gemMat(c))
      gem.position.set(x, 0.02, z)
      gem.scale.set(1.1, 1.5, 0.7)          // flattened oval cabochon
      gem.lookAt(x * 3, 0.02, z * 3)         // face outward, tall axis stays vertical
      crown.add(gem)
    })

    // rounded prong points (between the gems) capped with gold ball finials
    const PRONGS = 6
    for (let i = 0; i < PRONGS; i++) {
      const a = ((i + 0.5) / PRONGS) * Math.PI * 2, x = Math.cos(a), z = Math.sin(a)
      const prong = new THREE.Mesh(gProng, gold); prong.position.set(x * 0.99, 0.78, z * 0.99); crown.add(prong)
      const ball = new THREE.Mesh(gFinial, gold); ball.position.set(x * 0.99, 1.12, z * 0.99); crown.add(ball)
    }

    crown.rotation.x = -0.05   // tip the top back a hair so we read it head-on
    scene.add(crown)

    scene.add(new THREE.AmbientLight(0xffffff, 0.22))
    const key = new THREE.DirectionalLight(0xfff2c8, 1.15); key.position.set(2.5, 3, 2.5); scene.add(key)

    let raf
    if (reduce) {
      crown.rotation.y = -0.35
      renderer.render(scene, camera)
    } else {
      const loop = () => { crown.rotation.y += 0.01; renderer.render(scene, camera); raf = requestAnimationFrame(loop) }
      loop()
    }

    return () => {
      if (raf) cancelAnimationFrame(raf)
      envTex.dispose(); pmrem.dispose()
      junk.forEach((d) => d.dispose && d.dispose())
      renderer.dispose()
      const gl = renderer.getContext()
      const lose = gl && gl.getExtension('WEBGL_lose_context')
      if (lose) lose.loseContext()
      if (renderer.domElement.parentNode) renderer.domElement.parentNode.removeChild(renderer.domElement)
    }
  }, [])
  return <div className="crown3d" ref={mountRef} aria-hidden="true" />
}
