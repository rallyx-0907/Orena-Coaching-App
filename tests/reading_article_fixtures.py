"""Realistic page shapes for main-article extraction tests. No network, no real site's markup."""
from __future__ import annotations

VOA_LIKE = """<!DOCTYPE html>
<html lang="en"><head>
<title>Scientists Warn Rivers Are Warming Faster - Learning English</title>
<meta property="og:title" content="Scientists Warn Rivers Are Warming Faster">
<link rel="canonical" href="https://news.example.org/a/rivers-warming/7001.html">
<script type="application/ld+json">{"@type":"NewsArticle","headline":"Scientists Warn Rivers Are Warming Faster",
"datePublished":"2026-05-02T09:30:00+00:00","author":{"@type":"Person","name":"Andrew Smith"}}</script>
<style>.x{color:red}</style>
</head><body>
<header class="site-header"><a href="/">Learning English</a><a href="/search">Search</a></header>
<nav class="main-nav"><a href="/a">Home</a><a href="/b">News</a><a href="/c">Level One</a></nav>
<main id="content">
<article class="media-article">
  <h1>Scientists Warn Rivers Are Warming Faster</h1>
  <div class="byline">By Andrew Smith</div>
  <video controls><source src="a.mp4">Your browser doesn't support HTML5</video>
  <figure><img src="r.jpg" alt="river"><figcaption>FILE - A river flows through a valley, April 1, 2026. (Reuters/Jane Doe)</figcaption></figure>
  <div class="wsw"><p>I'm Andrew Smith.</p></div>
  <div class="content">
    <p>Scientists say rivers around the world are warming faster than the air above them. The finding comes from a study of more than two thousand rivers over four decades.</p>
    <p>Warmer water holds less oxygen, which is a problem for fish. Many species need cold, clear water to lay their eggs, and they cannot easily move to new places.</p>
    <h2>What researchers found</h2>
    <p>The team measured temperatures at hundreds of stations, and the numbers rose almost everywhere. "We did not expect the change to be this steady," said one of the lead researchers.</p>
    <p>Cities and farms make the problem worse because they send warm runoff into streams. Planting trees along the banks can cool the water by several degrees, the study said.</p>
    <p>Local governments are now asking engineers how to protect the most threatened rivers before the next hot summer begins.</p>
  </div>
  <div class="words-in-story">
    <h2>Words in This Story</h2>
    <p><strong>runoff</strong> - n. water that flows over land into a stream</p>
    <p><strong>species</strong> - n. a group of living things of the same kind</p>
    <p><strong>threatened</strong> - adj. in danger of disappearing</p>
  </div>
  <p class="wrote">Andrew Smith wrote this story for Learning English.</p>
  <section class="comments" id="comments"><h3>Comments</h3>
    <a href="#c" class="btn">See comments</a>
    <p>This is a really good report and I think more people should read it because rivers matter to all of us every day.</p>
  </section>
  <div class="related"><h2>Related</h2>
    <ul><li><a href="/1">Fish Disappear From Warm Lakes</a></li><li><a href="/2">A Drought Returns To The West</a></li><li><a href="/3">New Dams Change Old Rivers</a></li></ul>
  </div>
  <button class="close">Close</button>
  <div class="about-learning"><h3>About Learning English</h3>
    <p><a href="/about">Learning English is a daily program for learners around the world.</a> <a href="/levels">Find out more</a></p>
    <ul><li><a href="/l1">Beginning Level</a></li><li><a href="/l2">Intermediate Level</a></li><li><a href="/l3">Advanced Level</a></li></ul>
  </div>
</article>
</main>
<footer><p>Copyright 2026 Example Media. All rights reserved.</p><a href="/privacy">Privacy</a></footer>
</body></html>"""

NASA_LIKE = """<html><head><title>New Telescope Finds Water Vapor on Distant Planet | Space Agency</title>
<meta name="author" content="Mia Torres"><meta property="article:published_time" content="2026-02-11T12:00:00Z">
</head><body>
<div class="site-banner"><a href="/">Space Agency</a> <a href="/missions">Missions</a> <a href="/news">News</a></div>
<div class="page">
 <div class="ad-slot">Sponsored: buy a telescope</div>
 <article class="article-page">
  <h1>New Telescope Finds Water Vapor on Distant Planet</h1>
  <p class="meta">Feb 11, 2026</p>
  <p>A new space telescope has found water vapor in the air of a planet that orbits a faraway star. The planet is about the size of Neptune, and it circles its star every three days.</p>
  <p>Astronomers studied the starlight that passed through the planet's atmosphere. Different gases take in different colors of light, so the pattern of missing colors acts like a fingerprint.</p>
  <p>The team found a strong signal for water. They also saw hints of carbon dioxide, which may help them learn how the planet formed.</p>
  <figure><img src="p.jpg"><figcaption>An artist's idea of the planet. Credit: Space Agency/Art Team</figcaption></figure>
  <p>The telescope will keep watching the planet for many months. Scientists hope the measurements will show whether clouds hide parts of the air.</p>
  <p>Observations like these prepare the way for larger missions that will look for signs of life on smaller, rocky worlds.</p>
  <div class="share-tools"><a href="#">Share on Facebook</a><a href="#">Share on X</a><a href="#">Email</a></div>
  <div class="recommended-stories"><h3>You May Also Like</h3>
   <a href="/s1">Probe Reaches Icy Moon</a> <a href="/s2">Rocket Test Delayed</a> <a href="/s3">Crew Returns Home</a></div>
 </article>
 <aside class="sidebar"><h3>Latest</h3><ul><li><a href="/x">Mission Update</a></li><li><a href="/y">Image of the Day</a></li></ul></aside>
</div>
<footer class="site-footer"><a href="/about">About</a> <a href="/contact">Contact</a> <p>Page last updated February 2026.</p></footer>
</body></html>"""

NOAA_LIKE = """<html><head><title>How Tides Work - Ocean Service</title></head><body>
<div id="skip"><a href="#main">Skip to main content</a></div>
<div class="top-bar"><a href="/">Home</a> | <a href="/topics">Topics</a> | <a href="/search">Search</a></div>
<main id="main" role="main">
 <h1>How Tides Work</h1>
 <div class="breadcrumbs"><a href="/">Home</a> &gt; <a href="/education">Education</a> &gt; Tides</div>
 <div class="body-copy">
  <p>Tides are the daily rise and fall of the ocean. They are caused mainly by the pull of the moon, and to a smaller degree by the pull of the sun.</p>
  <p>When the moon is closest to a part of Earth, the water there bulges toward it. A second bulge forms on the opposite side, so most coasts see two high tides a day.</p>
  <h2>Spring and neap tides</h2>
  <p>When the sun, moon and Earth line up, their combined pull makes especially high and low tides. These are called spring tides, and they have nothing to do with the season.</p>
  <p>When the sun and moon pull at right angles, the tides are weaker. Those are called neap tides, and they happen twice every month.</p>
  <p>Knowing the tides helps sailors, fishers and swimmers plan their day safely along the shore.</p>
 </div>
 <div class="newsletter-signup"><h3>Get our newsletter</h3><form><input type="email"><button>Subscribe</button></form></div>
 <div class="page-meta">Last updated: June 3, 2025</div>
</main>
<footer role="contentinfo"><ul><li><a href="/p">Privacy Policy</a></li><li><a href="/d">Disclaimer</a></li><li><a href="/a">Accessibility</a></li></ul></footer>
</body></html>"""

BLOG_LIKE = """<html><head><title>Why I Started Baking Bread | Kitchen Notes</title></head><body>
<div id="wrapper">
 <div id="header"><div class="logo"><a href="/">Kitchen Notes</a></div>
  <ul class="menu"><li><a href="/">Home</a></li><li><a href="/recipes">Recipes</a></li><li><a href="/about">About</a></li><li><a href="/contact">Contact</a></li></ul></div>
 <div id="container">
  <div class="post">
   <h2 class="post-title">Why I Started Baking Bread</h2>
   <div class="post-meta">Posted on March 9 by Lena</div>
   <div class="entry">
    <p>Last winter I decided to bake all of our bread at home. I had never made anything more difficult than toast, so the first loaf came out flat and very hard.</p>
    <p>My neighbor told me to be patient. Bread needs time, she said, and the dough should rest until it has almost doubled in size.</p>
    <p>After a few weeks I learned to feel when the dough was ready. It should be soft and a little sticky, and it should spring back slowly when pressed.</p>
    <p>Now the whole house smells wonderful on Sunday mornings, and my children ask to help with the kneading.</p>
   </div>
   <div class="post-tags">Tags: <a href="/t/bread">bread</a>, <a href="/t/home">home</a>, <a href="/t/learning">learning</a></div>
  </div>
  <div id="comments"><h3>4 Responses</h3><ol><li><p>Great post, I will try this at the weekend with my sister and her family.</p></li></ol></div>
  <div class="related-posts"><h3>Related Posts</h3><ul><li><a href="/p1">Five Easy Soups</a></li><li><a href="/p2">My Favorite Knife</a></li><li><a href="/p3">Cooking For Two</a></li></ul></div>
 </div>
 <div id="sidebar"><h3>About Me</h3><p><a href="/about">Hi, I am Lena and I write about food.</a></p><h3>Archives</h3><ul><li><a href="/2026/03">March 2026</a></li><li><a href="/2026/02">February 2026</a></li></ul></div>
 <div id="footer">Copyright Kitchen Notes. Powered by BlogEngine.</div>
</div>
</body></html>"""

CHINESE_NEWS = """<html><head><title>河流水温上升 - 新闻网</title></head><body>
<nav><a href="/">首页</a><a href="/n">新闻</a></nav>
<article><h1>河流水温上升</h1>
<p>科学家说，世界各地的河流正在变暖，速度比空气还快。这项研究分析了四十年来两千多条河流的数据。</p>
<p>水温升高会让水里的氧气减少，这对鱼类是个问题。许多鱼需要清凉的水才能产卵，而且它们很难搬到别处。</p>
<p>城市和农田把温暖的雨水排进小溪，使问题更严重。沿河植树可以让水温下降几度。</p>
<p>各地政府正在请工程师研究，如何在下一个炎热的夏天到来之前保护最危险的河流。</p>
</article>
<div class="related"><a href="/1">相关新闻一</a><a href="/2">相关新闻二</a></div>
<footer>版权所有</footer></body></html>"""
