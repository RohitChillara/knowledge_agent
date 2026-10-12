import spacy

class Extraction:
    nlp=spacy.load("en_core_web_lg")

    def __init__(self,text):
        self.text=text

    def triple_extraction(self):
        doc=Extraction.nlp(self.text)
        for token in doc:
            subject_tokens=set()
            subjects=set()
            subject=None
            if token.dep_ in ("ROOT", "relcl", "conj", "ccomp", "advcl") and any(child.dep_ in ("nsubj","nsubjpass") for child in token.children):
                for child in token.children:
                    if child.dep_ in ("nsubj","nsubjpass") and child.pos_ not in ("PRON","NUM"):
                        subject=child.text
                        for ent in doc.ents:
                            if(ent.start<=child.i and ent.end>child.i):
                                subject=ent.text
                        subjects.add(subject)
                        subject_tokens.add(child)
                if subject==None and token.dep_=="relcl":
                        subject=token.head
                        for ent in doc.ents:
                            if(ent.start<=child.i and ent.end>child.i):
                                subject=ent.text

                for child in token.children:
                    if child.dep_ in ("prep","dobj", "attr"):
                        print(token.lemma_,child.text)

                                              
                   
               


    def test(self):
        doc = Extraction.nlp(self.text)
        for token in doc:
            print("dep ->"+ str(token.dep_)+" head->"+str(token.head)+" head pos->"+str(token.head.pos_))





if __name__=='__main__':
    test4="""Dr. Maria Santos, a physicist, and her students, Tom Baker and Priya Nair,
    published a study last spring. The study, which examined climate patterns
    across three continents, was funded by both the National Science
    Foundation and a private donor. Either the university or the ministry will
    host next year's conference. Santos, who leads the climate research group,
    previously worked at Stanford before moving to Oslo. A committee reviewed
    the proposal, and it approved additional funding. The lab, together with
    its partner institution, is expanding into new research areas.There were three researchers, 
    including Santos and her colleague Baker, who contributed significantly to the project; one of them later became the
    lab's director.
    """

    test5=""""Santos, who leads the research group, worked at Stanford."""
    obj=Extraction(test5)
    #obj.triple_extraction()
    obj.test()