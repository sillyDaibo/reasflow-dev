% csam.cls -- For CSIAM Transaction on Applied Mathematics
% This class file is made available for use by authors who wish to
% prepare an article for publication in the CSIAM Transaction on Applied Mathematics. The user may not exploit any part of the class
% file commercially.
%
% This class file is provided on an 'as is' basis. Authors are not allowed
% to change this file.
%
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{csiam-am}
      [2020/04/02 v1.0 Class for CSIAM Transaction on Applied Mathematics]

% v1.1 changes : bibliography size
% v1.2 changes : left margin of abstract
% v1.2.1 changes : \sc keywords
% v1.2.2 changes : \bf keywords \bf Abstract \it address
% v1.3 changes : change caption to font small
% v1.3.1 changes : package amsthm added
% v1.4 changes : package cite added, swap even-odd marks
% v1.5 changes : package ifthen added, modify \author command and add options:
%                odd, even: to tell first page number of the article is 
%                          odd or even 
%                   review: review article
%                    draft: a galley version (pages lineno and draftcopy required)
% v1.5.5 changes : option onepage added, for abstract end at the first page
% v1.6 changes : change left and right margin and change caption to \sf
% v1.6.5 changes : add option starteven for telling the issue starting page
%                  is even, this option should apply to whole issue, if so. 
%                  which will control the oddside and evenside margin
%                  caption changed also.
% v1.6.6 changes : update lemma and definiton style
% v1.6.7 changes : update \thisyear in copyright info
% v1.6.8 changes : proposition added
% v2.0 changes : change font starting from volume two, use package mathpazo
%                remove \authaddr but 
%                add \emails (or \email) for author(s) email address(es)
%                    usage: \email{{\tt address@xxx} (T.~Lam)) % for single author
%                           \emails for more than one authors
%                add \ams and \pac for AMS and PACs numbers
%                add newenvironment FloatAlgo for algorithm
%                    usage: \begin{FloatAlgo}{caption here.} ... \end{FloatAlgo}
% v2.0.1 changes : make changes on subsubsection spacing.
% v2.0.2 changes : having \pacs for PACS (2006)
% v2.1 changes: package mathpazo as an option, instead of default loaded

\LoadClass[twoside,11pt,a4paper]{article}

\RequirePackage{graphicx}
\RequirePackage{amsfonts,amssymb,amsbsy,amsmath,amsthm}
\RequirePackage{ifthen}


\newboolean{PG@odd}  % set true for first page number is odd
\newboolean{REV@art} % set true for Review Article
\newboolean{SN@art}
\newboolean{CODE@art}
\newboolean{DRAFT@copy} % set true for Draft copy
\newboolean{ONE@page} % set true for the first page end at abstract
\newboolean{START@even} % set true for the book first page is even
\newboolean{PAZO@load} % set true for mathpazo load
\setboolean{PG@odd}{true}
\setboolean{REV@art}{false}
\setboolean{SN@art}{false}
\setboolean{CODE@art}{false}
\setboolean{DRAFT@copy}{false}
\setboolean{ONE@page}{false}
\setboolean{START@even}{false}
\setboolean{PAZO@load}{false}
\DeclareOption{odd}{\setboolean{PG@odd}{true}}
\DeclareOption{even}{\setboolean{PG@odd}{false}}
\DeclareOption{review}{\setboolean{REV@art}{true}}
\DeclareOption{shortnote}{\setboolean{SN@art}{true}}
\DeclareOption{code}{\setboolean{CODE@art}{true}}
\DeclareOption{draft}{\setboolean{DRAFT@copy}{true}}
\DeclareOption{onepage}{\setboolean{ONE@page}{true}}
\DeclareOption{starteven}{\setboolean{START@even}{true}}
\DeclareOption{mathpazo}{\setboolean{PAZO@load}{true}}

\ProcessOptions

% general setting
\ifthenelse{\boolean{PAZO@load}}
{\RequirePackage{mathpazo}}
{}
\setlength{\textwidth}{150mm}
\setlength{\textheight}{200mm}
\setlength{\topmargin}{-0mm}
%\setlength{\oddsidemargin}{5mm}
%\setlength{\evensidemargin}{5mm}
\setlength{\oddsidemargin}{8mm}
\setlength{\evensidemargin}{-2mm}
\ifthenelse{\boolean{START@even}}
{ \setlength{\oddsidemargin}{-2mm} 
  \setlength{\evensidemargin}{8mm} }
{}
%\setlength\footskip{30\p@} % original setting
%\setlength\footnotesep{7.7\p@}
%\setlength{\skip\footins}{10\p@ \@plus 4\p@ \@minus 2\p@}
%\setlength\footskip{15\p@}
\setlength\footnotesep{3.5\p@}
%\setlength{\skip\footins}{5\p@ \@plus 2\p@ \@minus 1\p@}

\newlength{\titleright}
\setlength{\titleright}{3cm}

\AtBeginDocument{
  \immediate\write\@auxout{\string
  \newlabel{FirstPage}{{}{\thepage}}}
}

\AtEndDocument{
  \clearpage\addtocounter{page}{-1}
  \immediate\write\@auxout{\string
  \newlabel{LastPage}{{}{\thepage}}}
  \addtocounter{page}{1}
}

\newcommand\journalname{CSIAM Transaction on Applied Mathematics}
\newcommand\thisnumber{1}
\newcommand\thisyear {202x}
\newcommand\thismonth{February}
\newcommand\thisvolume{x}
\newcommand\doi{}

\def\thispagestart{\pageref{FirstPage}}
\def\thispageend{\pageref{LastPage}}

\def\ps@firstpage{\ps@empty
  \def\@oddfoot{\footnotesize http://www.global-sci.org/csiam-am \hfil \thepage \hfil 
                \copyright \thisyear\  Global-Science Press}
  \let\@evenfoot\@oddfoot
%  \def\@oddhead{\usebox{\lheadbox} \hfil \usebox{\rheadbox}
  \def\@oddhead{
      \parbox{9cm}{\footnotesize CSIAM~Trans.~Appl.~Math. 
\\ doi:~\doi}
  \hfil
      \parbox{4cm}{\footnotesize Vol.~{\bf\thisvolume}, No.~\thisnumber, pp.~\thispagestart-\thispageend 
\\ \thismonth \  \thisyear}
  }
  \let\@evenhead\@oddhead % in case an article starts on a left-hand page
  \let\@mkboth\@empty
}
\def\ps@headings{%
      \let\@oddfoot\@empty\let\@evenfoot\@empty
%      \def\@oddhead{\footnotesize \thepage\hfil\leftmark}%
%      \def\@evenhead{\footnotesize \rightmark\hfil\thepage}%
\ifthenelse{\boolean{PG@odd}}
      { \def\@evenhead{\footnotesize \thepage\hfil\leftmark}   % The first page number is odd
        \def\@oddhead{\footnotesize \rightmark\hfil\thepage} } %
      { \def\@oddhead{\footnotesize \thepage\hfil\leftmark}    % The first page number is even
        \def\@evenhead{\footnotesize \rightmark\hfil\thepage} }%
      \let\@mkboth\markboth
}

\renewcommand\maketitle{\par
   \begingroup
   \global\@topnum\z@
   \@maketitle
   \thispagestyle{firstpage}
   \endgroup
   \global\let\thanks\relax
   \global\let\maketitle\relax
   \global\let\@maketitle\relax
   \global\let\@thanks\@empty
   \global\let\@author\@empty
   \global\let\@date\@empty
   \global\let\@title\@empty
   \global\let\title\relax
   \global\let\author\relax
   \global\let\date\relax
   \global\let\and\relax
}

%
\renewcommand\@maketitle{
  \normalfont\normalsize
  \global\topskip8\p@\relax % 5.5pc   "   "   "     "     "
  \vfil\null
%  \vskip 30\p@
  \@settitle
  \ifx\@empty\author 
     \else 
         \@setauthor 
         \markboth
          {\ifx\@empty\shortauthor {\footnotesize\@author}
\else {\footnotesize \noexpand\shortauthor} \fi
{\footnotesize /  CSIAM~Trans.~Appl.~Math., {\bf \thisvolume} (\thisyear), pp.~\thispagestart-\thispageend } 
}
          {\ifx\@empty\shortauthor {\footnotesize\@author} \else {\footnotesize \noexpand\shortauthor} 
{\footnotesize /  CSIAM~Trans.~Appl.~Math., {\bf \thisvolume} (\thisyear), pp.~\thispagestart-\thispageend } 
\fi}
%          {\ifx\@empty\shorttitle {\footnotesize\@title} \else {\footnotesize \shorttitle} \fi}
%          {\ifx\@empty\shortauthor {\footnotesize\@author} \else {\footnotesize \shortauthor} \fi}
  \fi
  \ifx\@empty\@address \else \@setaddress \fi
\noindent\hrulefill
  \@setabstract 
  \vspace{-12pt}
  \ifx\@empty\@both\else \@setboth\fi
  \ifx\@empty\@ams\else \@setams\fi
  \ifx\@empty\@pac\else \@setpac\fi
  \ifx\@empty\@pacs\else \@setpacs\fi
  \ifx\@empty\@keywords\else \@setkeywords\fi
  \ifthenelse{\boolean{ONE@page}}
  {}
  {\noindent\hrulefill}
  \normalsize
}

% footnote for corr author


%\setlength{\skip\footins}{2.5pc}
\renewcommand{\footnoterule}{\noindent\rule{5pc}{0.25pt}\vspace*{6pt}}
\renewcommand{\thefootnote}{\fnsymbol{footnote}}
\long\def\@makefntext#1{\parindent 1em
\noindent{$\m@th^{\@thefnmark}$}#1}

%\def\corraddr#1{\footnotetext[1]{Correspondence to: #1}\stepcounter{footnote}}
\def\corraddr#1{} % do not need address anymore!


\def\email#1{\def\@email{#1}}
\let\@email=\@empty
\def\@setemail{{\it Email address:} \@email}

\def\emails#1{\def\@emails{#1}}
\let\@emails=\@empty
\def\@setemails{{\it Email addresses:} \@emails}

\def\corrauth{\footnotemark[1]\footnotetext[1]{Corresponding author.
 \ifx\@empty\@email\else \@setemail\fi
 \ifx\@empty\@emails\else \@setemails\fi}\stepcounter{footnote}}



\def\affilnum#1{${}^{#1}$}
\def\affil#1{${}^{#1}$}
\def\comma{$^{\textrm{,}}$}

%%%%%%%%%%%%%%%%%%%%%%%%%%

% define environment for title and author
\newenvironment{titquote}{\begin{list}{}
{\setlength{\leftmargin}{0pt}
 \setlength{\rightmargin}{\titleright}
 \setlength{\topsep}{6pt}
 \setlength{\parskip}{0pt}}
 \item[]}{\end{list}}
%
% Article titles
%
% Usage: \title[Short title]{Full title}
% [Short title] is optional; use where title is too long
% or contains footnotes, 50 characters maximum
%
\renewcommand*{\title}[2][]{\gdef\shorttitle{#1}\gdef\@title{#2}}
\let\shorttitle=\empty
\def\@settitle{
%  \begin{center}%
  %\baselineskip14\p@\relax
  \begin{titquote}
  \Large  \bfseries
  \ifthenelse{\boolean{REV@art}}
  {  \item[]
     {\LARGE R}{\large EVIEW }{\LARGE A}{\large RTICLE} } % For Review Article
  {}
  \ifthenelse{\boolean{SN@art}}
  {  \item[]
     {\LARGE S}{\large HORT }{\LARGE N}{\large OTE} } % For Short Note
  {}
    \ifthenelse{\boolean{CODE@art}}
  {  \item[]
     {\LARGE C}{\large OMPUTATIONAL }{\LARGE S}{\large OFTWARE} } % For Code
  {}
  \item[]
  \@title
%  \end{center}%
  \end{titquote}
}
%
% List of authors
%
% Usage \author[Short form]{List of all authors}
% The short form excludes footnote symbols linking authors to addresses
% and is used for running heads in printed version (but not on preprints)
%
\let\shortauthor=\empty
\renewcommand*{\author}[2][?]{
     \gdef\shortauthor{?} 
     \gdef\@author{#2}
   \ifthenelse{\equal{#1}{?}}
     { \gdef\shortauthor{\let\comma=\empty \let\corrauth=\empty \renewcommand{\affil}[1]{} #2} }
     { \gdef\shortauthor{#1}}
}
\def\@setauthor{%\begin{center}%
  %\bfseries
  \begin{titquote}
  \large 
%  \item[]
  \@author
  \end{titquote}
%  \end{center}%
}

%
% Affiliation (authors address)
%
% Usage: \address{Address of first author}
%        \address{Address of second author}
% Use once for each address, use symbols \dag \ddag \S \P $\|$
% to connect authors with addresses
%
\def\address#1{\def\@address{#1}}
\let\@address=\@empty
\def\@setaddress{\vspace{-12pt}
   \begin{titquote}
   %\rm\small \@address
   \rm\it\small \@address
   \end{titquote}
}
%
\def\keywords#1{\def\@keywords{#1}}
\let\@keywords=\@empty
\def\@setkeywords{
     \addtolength{\topsep}{-6pt}
     \begin{trivlist}
     %\item[]\rm\small {\sc\small Key words}: \@keywords
     \item[]\rm\small {\bf\small Key words}: \@keywords
     \end{trivlist}
}
%
%
% AMS or PACS
% Usage: \both{57.XX, 58.XX}
%
\def\both#1{\def\@both{#1}}
\let\@both=\@empty
\def\@setboth{
     \addtolength{\topsep}{-6pt}
     \begin{trivlist}
     \item[]\rm\small {\bf \small AMS subject classifications or PACS}: \@both
     \end{trivlist}
}
%
% American Mathematical Society Classification Numbers
% Usage: \ams{57.XX, 58.XX}
%
\def\ams#1{\def\@ams{#1}}
\let\@ams=\@empty
\def\@setams{
     \addtolength{\topsep}{-6pt}
     \begin{trivlist}
     \item[]\rm\small {\bf \small AMS subject classifications}: \@ams
     \end{trivlist}
}
%
% Physics & Astronomy Classification Numbers (more than one)
% Usage \pacs{31.10, 31.20T}
%
\def\pac#1{\def\@pac{#1}}
\let\@pac=\@empty
\def\@setpac{
     \addtolength{\topsep}{-6pt}
     \begin{trivlist}
     \item[]\rm\small {\bf\small PACS}: \@pac
     \end{trivlist}
}
%
% Physics & Astronomy Classification Numbers (2006) (more than one)
% Usage \pacs{31.10, 31.20T}
%
\def\pacs#1{\def\@pacs{#1}}
\let\@pacs=\@empty
\def\@setpacs{
     \addtolength{\topsep}{-6pt}
     \begin{trivlist}
     \item[]\rm\small {\bf\small PACS (2006)}: \@pacs
     \end{trivlist}
}
%
\newbox\abstractbox
%\renewenvironment{abstract}{%
%      \vspace{6pt plus3pt minus3pt}
%      \begin{quote}
%%      \item[]{\bfseries \abstractname.}\quad\rm\ignorespaces}
%      \rm\ignorespaces}
%      {\end{quote}\if@titlepage\newpage\else\vspace{0\p@ plus0\p@}\fi}
\renewenvironment{abstract}{%
  \ifx\maketitle\relax
    \ClassWarning{\@classname}{Abstract should precede
      \protect\maketitle\space in AMS documentclasses; reported}%
  \fi
  \global\setbox\abstractbox=\vtop \bgroup
    \normalfont\small
    \list{}{\labelwidth\z@
      % comment in v1.2
      % \leftmargin6pc %\rightmargin\leftmargin
      \leftmargin4pc %\rightmargin\leftmargin
       \itemindent\z@
      \parsep\z@ \@plus\p@
      \let\fullwidthdisplay\relax
    }%
    % v change Abstract from sc -> bf
    %\item[\hskip\labelsep\scshape\abstractname.]%
    \item[\hskip\labelsep\bfseries\abstractname.]%
}{%
  \endlist\egroup
  \ifx\@setabstract\relax \@setabstracta \fi
}
\def\@setabstract{\@setabstracta \global\let\@setabstract\relax}
\def\@setabstracta{%
  \ifvoid\abstractbox
  \else
    \skip@6\p@ \advance\skip@-\lastskip
    \advance\skip@-\baselineskip \vskip\skip@
    \box\abstractbox
    \prevdepth\z@ % because \abstractbox is a vtop
  \fi
}

% caption in small font
\long\def\@makecaption#1#2{%
  \renewcommand{\baselinestretch}{0.5}\rm
  \vskip\abovecaptionskip
  \sbox\@tempboxa{\sf \footnotesize #1: #2}%
  \ifdim \wd\@tempboxa >\hsize
    {\sf \footnotesize #1: #2}\par
  \else
    \global \@minipagefalse
    \hb@xt@\hsize{\hfil\box\@tempboxa\hfil}%
  \fi
  \vskip\belowcaptionskip
  \renewcommand{\baselinestretch}{1}\rm
}


\renewenvironment{thebibliography}[1]
     {\section*{\small \refname}%
      %\@mkboth{\MakeUppercase\refname}{\MakeUppercase\refname}%
      \list{\@biblabel{\@arabic\c@enumiv}}%
           {\settowidth\labelwidth{\@biblabel{#1}}%
            \leftmargin\labelwidth
            \parsep 0ex
            \itemsep 0ex
            \advance\leftmargin\labelsep
            \@openbib@code
            \usecounter{enumiv}%
            \let\p@enumiv\@empty
            \renewcommand\theenumiv{\@arabic\c@enumiv}
            \small }%
      \sloppy
      \clubpenalty4000
      \@clubpenalty \clubpenalty
      \widowpenalty4000%
      \sfcode`\.\@m}
     {\def\@noitemerr
       {\@latex@warning{Empty `thebibliography' environment}}%
      \endlist}
      
% Define an environment for algorithms.
\newcounter{Algctr}[section]
\renewcommand{\theAlgctr}{\thesection.\arabic{Algctr}}
\newenvironment{FloatAlgo}[1]{%
  \refstepcounter{Algctr}%
  \begin{table}[!t]
    \noindent{\sf \footnotesize  Algorithm~\theAlgctr}: {\sf \footnotesize  #1} \\ %
    \rule{\textwidth}{2pt}
 %   \nopagebreak%
    \small\sf %
   }
   {
    \vspace{-0.4cm}
    \rule{\textwidth}{2pt}
    \end{table}%
    \normalsize%
  }      

% Misc
\newtheorem{theorem}{Theorem}[section]
\newtheorem{lemma}{Lemma}[section]
\newtheorem{corollary}{Corollary}[section]
\newtheorem{proposition}{Proposition}[section]
\newtheorem{definition}{Definition}[section]

\theoremstyle{definition}
\newtheorem{example}{Example}[section]
\newtheorem{remark}{Remark}[section]
\numberwithin{equation}{section}


\pagestyle{headings}

\ifthenelse{\boolean{DRAFT@copy}}  % if it is a draftcopy
{ \usepackage{draftcopy}
  \draftcopyName{ Galley Proof}{144}
  \usepackage{lineno}
  \linenumbers }
{}

\thickmuskip=2mu plus 2mu minus 2mu
%\medmuskip=1mu plus 1mu minus 1mu
\medmuskip=1mu minus 1mu
\thinmuskip=1mu

% original article parameter
%\newcommand\section{\@startsection {section}{1}{\z@}%
%                                   {-3.5ex \@plus -1ex \@minus -.2ex}%
%                                   {2.3ex \@plus.2ex}%
%                                   {\normalfont\Large\bfseries}}
%\newcommand\subsection{\@startsection{subsection}{2}{\z@}%
%                                     {-3.25ex\@plus -1ex \@minus -.2ex}%
%                                     {1.5ex \@plus .2ex}%
%                                     {\normalfont\large\bfseries}}
%\newcommand\subsubsection{\@startsection{subsubsection}{3}{\z@}%
%                                     {-3.25ex\@plus -1ex \@minus -.2ex}%
%                                     {1.5ex \@plus .2ex}%
%                                     {\normalfont\normalsize\bfseries}}
\renewcommand\subsubsection{\@startsection{subsubsection}{3}{\z@}%
                                     {-2ex\@plus -1ex \@minus -.2ex}%
                                     {1ex \@plus .2ex}%
                                     {\normalfont\normalsize\bfseries}}


\endinput
